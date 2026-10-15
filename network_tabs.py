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
    def __init__(self, parent):
        self.choice = tk.StringVar(value="192.168.10.10")
        self.custom = tk.StringVar(value="192.168.10.10")
        box = ttk.LabelFrame(parent, text="Target IP", padding=8)
        box.pack(fill="x", pady=6)
        selector = ttk.Combobox(
            box,
            textvariable=self.choice,
            values=("192.168.10.10", "192.168.10.16", "Custom"),
            state="readonly",
            width=20,
        )
        selector.pack(side="left")
        self.entry = ttk.Entry(box, textvariable=self.custom, width=20)
        ttk.Label(box, text="Mask 255.255.255.0 | UDP 4660 | timeout 3 s").pack(
            side="right"
        )
        self.choice.trace_add("write", lambda *unused: self.show_custom())

    def show_custom(self):
        if self.choice.get() == "Custom":
            self.entry.pack(side="left", padx=8)
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
        notebook.add(clock_page, text="set_cdce62002")
        notebook.add(writer_page, text="MPC / MPCX / IP")
        file_box = ttk.LabelFrame(self.writer, text="MPC / MPCX file", padding=8)
        file_box.pack(fill="x", pady=(0, 6))
        ttk.Entry(file_box, textvariable=self.file, state="readonly").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(file_box, text="Choose file", command=self.choose_file).pack(
            side="left", padx=6
        )
        self.file_status = tk.StringVar(
            value="No file selected. IP-only operations do not require a license file."
        )
        ttk.Label(self.writer, textvariable=self.file_status, wraplength=900).pack(
            anchor="w"
        )
        self.clock_target = TargetAddress(self.clock)
        self.writer_target = TargetAddress(self.writer)
        for tab in (self.clock, self.writer):
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
            self.writer,
            text="New device IP (optional for license writes; required for IP-only writes)",
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
        for name in ("Read", "Check", "Write MPC/MPCX", "Write IP only"):
            ttk.Button(
                actions, text=name, command=lambda action=name: self.utility(action)
            ).pack(side="left", padx=4)
        ttk.Label(
            self.writer,
            text="Files are validated by content and checked against device generation. Writes use the referenced utility's readback verification. No automatic Clear or reset is performed.",
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
        self.writer_target.set("192.168.10.10" if kind == "MPCX" else "192.168.10.16")

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
            host = self.writer_target.value()
            command = operations.utility_command(
                self.root_path,
                host,
                action,
                self.file.get(),
                self.new_ip.get(),
                self.current.get(),
                self.initialize.get(),
            )
        except Exception as error:
            messagebox.showerror("Network operation", str(error))
            return
        changes = action.startswith("Write")
        new_endpoint = (
            self.new_ip.get().strip() if self.current.get() and changes else ""
        )
        if changes and not messagebox.askyesno(
            action,
            f"{self.board.get()} at {host}\n{action}\nFile: {self.file.get() or '(none)'}\nNew IP: {self.new_ip.get() or '(unchanged)'}\nContinue?",
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
