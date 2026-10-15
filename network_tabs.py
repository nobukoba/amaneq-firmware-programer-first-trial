"""Network configuration tabs; all hardware writes require explicit buttons."""

import subprocess
import sys
from tkinter import filedialog, messagebox, ttk
import tkinter as tk
import network_operations as operations


class NetworkTabs:
    def __init__(self, notebook, board, root_path, task, events, network_widgets):
        self.board = board
        self.root_path = root_path
        self.task = task
        self.events = events
        self.mode = tk.StringVar(value="MPCX")
        self.custom = tk.StringVar(value="192.168.10.10")
        self.preset = tk.StringVar(value=next(iter(operations.PRESETS)))
        self.persist = tk.BooleanVar(value=True)
        self.file = tk.StringVar()
        self.new_ip = tk.StringVar()
        self.current = tk.BooleanVar(value=False)
        self.initialize = tk.BooleanVar(value=False)
        self.status = tk.StringVar()
        self.clock = ttk.Frame(notebook, padding=10)
        self.writer = ttk.Frame(notebook, padding=10)
        notebook.add(self.clock, text="set_cdce62002")
        notebook.add(self.writer, text="MPC / MPCX / IP")
        for tab in (self.clock, self.writer):
            connection = ttk.LabelFrame(
                tab, text="Target connection (UDP 4660; timeout 3 s)", padding=8
            )
            connection.pack(fill="x", pady=5)
            ttk.Label(connection, text="Device mode").grid(row=0, column=0)
            mode_box = ttk.Combobox(
                connection,
                textvariable=self.mode,
                values=("MPCX", "MPC", "Custom"),
                state="readonly",
                width=12,
            )
            mode_box.grid(row=0, column=1, padx=6)
            ttk.Label(connection, text="Target IP").grid(row=0, column=2)
            ip_entry = ttk.Entry(connection, textvariable=self.custom, width=18)
            ip_entry.grid(row=0, column=3, padx=6)
            ttk.Label(connection, text="Subnet mask: 255.255.255.0").grid(
                row=0, column=4
            )

            def selected(unused=None, entry=ip_entry):
                if self.mode.get() != "Custom":
                    self.custom.set(operations.endpoint(self.mode.get(), ""))
                entry.configure(
                    state="normal" if self.mode.get() == "Custom" else "readonly"
                )

            mode_box.bind("<<ComboboxSelected>>", selected)
            self.mode.trace_add("write", lambda *unused, callback=selected: callback())
            selected()
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
            text="Copy verified settings to CDCE62002 EEPROM (hul-common-lib default)",
            variable=self.persist,
        ).pack(anchor="w")
        ttk.Button(
            self.clock, text="Apply clock setting", command=self.configure_clock
        ).pack(anchor="w", pady=10)
        file_box = ttk.LabelFrame(
            self.writer, text="MPC / MPCX license file", padding=8
        )
        file_box.pack(fill="x", pady=8)
        ttk.Entry(file_box, textvariable=self.file).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(
            file_box,
            text="Choose file",
            command=self.choose_file,
        ).pack(side="left")
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
        if self.mode.get() != "Custom":
            self.mode.set(kind)

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
            host = operations.endpoint(self.mode.get(), self.custom.get())
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
            host = operations.endpoint(self.mode.get(), self.custom.get())
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
