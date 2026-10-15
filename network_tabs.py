"""Network configuration tabs; all hardware writes require explicit buttons."""

import subprocess
import sys
from tkinter import filedialog, messagebox, ttk
import tkinter as tk
import network_operations as operations


def scrollable_tab(notebook):
    outer = ttk.Frame(notebook)
    canvas = tk.Canvas(outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    body = ttk.Frame(canvas, padding=10)
    window = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind(
        "<Configure>", lambda unused: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.bind(
        "<Configure>", lambda event: canvas.itemconfigure(window, width=event.width)
    )
    return outer, body


class TargetAddress:
    def __init__(self, parent, task, events):
        self.task = task
        self.events = events
        self.choice = tk.StringVar(value="192.168.10.10")
        self.custom = tk.StringVar(value="192.168.10.10")
        box = ttk.Frame(parent)
        box.pack(fill="x", pady=6)
        ttk.Label(box, text="Target IP").pack(side="left", padx=(0, 8))
        selector = ttk.Combobox(
            box,
            textvariable=self.choice,
            values=("192.168.10.10", "192.168.10.16", "Custom"),
            state="readonly",
            width=20,
        )
        selector.pack(side="left")
        self.entry = ttk.Entry(box, textvariable=self.custom, width=20)
        self.ping_button = ttk.Button(box, text="Ping", command=self.ping)
        self.ping_button.pack(side="left", padx=8)
        self.ping_status = tk.StringVar()
        ttk.Label(box, textvariable=self.ping_status).pack(side="left")
        self.choice.trace_add("write", lambda *unused: self.show_custom())
        self.custom.trace_add("write", lambda *unused: self.ping_status.set(""))

    def ping(self):
        try:
            host = self.value()
        except ValueError as error:
            messagebox.showerror("Target IP", str(error))
            return
        if self.ping_button.instate(["disabled"]):
            return
        self.ping_button.state(["disabled"])
        self.ping_status.set("Pinging...")

        def operation():
            try:
                success, output = operations.ping_target(host)
                status = "Reply received" if success else "No ICMP reply"
            except Exception as error:
                status, output = "Ping failed", str(error)
            self.events.put(("log", f"Ping {host}: {status}\n{output}"))
            return "ping", (self, host, status)

        self.task(f"Ping {id(self)} {host}", operation)

    def ping_result(self, host, status):
        self.ping_button.state(["!disabled"])
        current = (
            self.custom.get() if self.choice.get() == "Custom" else self.choice.get()
        )
        self.ping_status.set(status if current.strip() == host else "")

    def show_custom(self):
        self.ping_status.set("")
        if self.choice.get() == "Custom":
            self.entry.pack(side="left", padx=8, before=self.ping_button)
        else:
            self.entry.pack_forget()

    def value(self):
        return operations.ipv4(
            self.custom.get() if self.choice.get() == "Custom" else self.choice.get()
        )

    def set(self, address):
        address = operations.ipv4(address)
        if address in ("192.168.10.10", "192.168.10.16"):
            self.choice.set(address)
        else:
            self.custom.set(address)
            self.choice.set("Custom")


class NetworkTabs:
    def __init__(self, notebook, board, root_path, task, events, network_widgets):
        self.board = board
        self.root_path = root_path
        self.task = task
        self.events = events
        self.preset = tk.StringVar(value=next(iter(operations.PRESETS)))
        self.persist = tk.BooleanVar(value=True)
        self.file = tk.StringVar()
        self.new_ip = tk.StringVar()
        self.current = tk.BooleanVar(value=False)
        self.initialize = tk.BooleanVar(value=False)
        self.status = tk.StringVar()
        clock_page, self.clock = scrollable_tab(notebook)
        writer_page, self.writer = scrollable_tab(notebook)
        ip_page, self.ip = scrollable_tab(notebook)
        notebook.add(writer_page, text="MPC / MPCX")
        notebook.add(ip_page, text="IP")
        notebook.add(clock_page, text="Jitter Cleaner")
        file_box = ttk.LabelFrame(self.writer, text="MPC / MPCX file", padding=8)
        file_box.pack(fill="x", pady=(0, 6))
        ttk.Entry(file_box, textvariable=self.file, state="readonly").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(file_box, text="Choose file", command=self.choose_file).pack(
            side="left", padx=6
        )
        self.file_status = tk.StringVar(
            value="No file selected. Choose an MPC/MPCX file to detect its type."
        )
        ttk.Label(self.writer, textvariable=self.file_status, wraplength=900).pack(
            anchor="w"
        )
        self.clock_target = TargetAddress(self.clock, task, events)
        self.writer_target = TargetAddress(self.writer, task, events)
        self.ip_target = TargetAddress(self.ip, task, events)
        for tab in (self.clock, self.writer, self.ip):
            network_widgets(tab)
        ttk.Label(self.clock, textvariable=self.status, wraplength=900).pack(
            anchor="w", pady=8
        )
        ttk.Label(self.clock, text="Select input / output frequencies (MHz):").pack(
            anchor="w"
        )
        ttk.Combobox(
            self.clock,
            textvariable=self.preset,
            values=tuple(operations.PRESETS),
            state="readonly",
            width=35,
        ).pack(anchor="w", pady=8)
        ttk.Checkbutton(
            self.clock,
            text="Save clock settings for the next power-on",
            variable=self.persist,
        ).pack(anchor="w")
        ttk.Button(
            self.clock, text="Apply clock setting", command=self.configure_clock
        ).pack(anchor="w", pady=10)
        ttk.Checkbutton(
            self.writer,
            text="Initialize XG EEPROM from current settings before license programming",
            variable=self.initialize,
        ).pack(anchor="w")
        ip_box = ttk.LabelFrame(
            self.ip,
            text="New device IP",
            padding=8,
        )
        ip_box.pack(fill="x", pady=8)
        ttk.Entry(ip_box, textvariable=self.new_ip, width=20).pack(side="left")
        ttk.Checkbutton(
            ip_box,
            text="Change current/runtime IP instead of saved EEPROM IP",
            variable=self.current,
        ).pack(side="left", padx=10)
        actions = ttk.Frame(self.writer)
        actions.pack(fill="x", pady=10)
        for name in ("Read", "Check", "Write MPC/MPCX"):
            ttk.Button(
                actions, text=name, command=lambda action=name: self.utility(action)
            ).pack(side="left", padx=4)
        ttk.Label(
            self.writer,
            text="Files are validated by content and checked against device generation. Writes use the referenced utility's readback verification. No automatic Clear or reset is performed.",
            wraplength=900,
        ).pack(anchor="w")
        ip_actions = ttk.Frame(self.ip)
        ip_actions.pack(fill="x", pady=10)
        ttk.Button(
            ip_actions, text="Read IP", command=lambda: self.utility("Read IP")
        ).pack(side="left", padx=4)
        ttk.Button(
            ip_actions, text="Write IP", command=lambda: self.utility("Write IP only")
        ).pack(side="left", padx=4)
        ttk.Label(
            self.ip,
            text="IP writes preserve MPC/MPCX license data. Saved EEPROM IP is the default; changing the current IP reconnects and verifies the new endpoint.",
            wraplength=900,
        ).pack(anchor="w")
        board.trace_add("write", lambda *unused: self.refresh_board())
        self.refresh_board()

    def choose_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("MPC/MPCX", "*.mpc *.mpcx"), ("All files", "*")]
        )
        if not path:
            return
        try:
            kind = operations.license_kind(path)
        except Exception as error:
            messagebox.showerror("MPC/MPCX file", str(error))
            return
        self.file.set(path)
        self.file_status.set(f"Detected from contents: {kind}")
        address = "192.168.10.10" if kind == "MPCX" else "192.168.10.16"
        self.writer_target.set(address)
        self.ip_target.set(address)

    def refresh_board(self):
        if self.board.get() == "CIRASAME":
            self.preset.set("in_125_out_500_125")
        self.status.set(
            "STAG clock register map is not verified; clock writes are unavailable."
            if self.board.get() == "STAG"
            else "HUL CDCE62002 register map. Confirm the selected board runs compatible firmware."
        )

    def configure_clock(self):
        if self.board.get() == "STAG":
            messagebox.showerror("Unsupported clock map", self.status.get())
            return
        try:
            host = self.clock_target.value()
        except ValueError as error:
            messagebox.showerror("Target IP", str(error))
            return
        preset, persist = self.preset.get(), self.persist.get()
        description = (
            "Registers and persistent CDCE62002 EEPROM"
            if persist
            else "Runtime CDCE62002 registers"
        )
        if messagebox.askyesno(
            "Configure clock",
            f"{self.board.get()} at {host}\n{preset}\n{description} will change. Continue?",
        ):
            self.task(
                "Clock configuration",
                lambda: ("log", operations.configure_clock(host, preset, persist)),
                changes=True,
            )

    def utility(self, action):
        try:
            ip_operation = action in ("Read IP", "Write IP only")
            selected_target = self.ip_target if ip_operation else self.writer_target
            host = selected_target.value()
            selected_file = "" if ip_operation else self.file.get()
            selected_new_ip = self.new_ip.get() if ip_operation else ""
            command = operations.utility_command(
                self.root_path,
                host,
                action,
                selected_file,
                selected_new_ip,
                self.current.get() if ip_operation else False,
                self.initialize.get() if not ip_operation else False,
            )
        except Exception as error:
            messagebox.showerror("Network operation", str(error))
            return
        changes = action.startswith("Write")
        new_endpoint = (
            selected_new_ip.strip()
            if self.current.get() and ip_operation and changes
            else ""
        )
        if changes and not messagebox.askyesno(
            action,
            f"{self.board.get()} at {host}\n{action}\nFile: {selected_file or '(none)'}\nNew IP: {selected_new_ip or '(unchanged)'}\nContinue?",
        ):
            return

        def operation():
            self.events.put(("log", subprocess.list2cmdline(command)))
            with subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            ) as process:
                for line in process.stdout:
                    self.events.put(("log", line.rstrip()))
                code = process.wait()
            if code:
                raise RuntimeError(
                    f"{action} failed (exit {code}). See the log; no automatic write retry was made."
                )
            if new_endpoint:
                self.events.put(("endpoint", new_endpoint))
            return "log", f"{action} completed."

        self.task(action, operation, changes=changes)
