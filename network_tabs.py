"""Network configuration tabs; all hardware writes require explicit buttons."""

import subprocess
import sys
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk
import network_operations as operations



HELP_TOPICS = {
    "jtag": [
        "JTAG cable and automatic detection",
        "JTAG is the hardware programming connection used to load the FPGA or write its flash. The JTAG cable is the USB programmer, not the Ethernet network adapter.\n\nConnected cables are automatically detected when the app starts. Press Rescan after connecting or disconnecting a cable. A single identified cable is selected automatically. If several cables are connected, choose the intended cable by its serial number; the app will not silently choose the first one.\n\nSome FT232H devices share the same USB identifier. That identifier alone does not prove the cable is an HS3. Confirm that an unidentified FT232H is physically an HS3 only when you have checked the hardware.\n\nScanning and opening this help do not program the board or change USB drivers. Program image starts firmware programming after the existing checks. USB access permissions or host-side setup may still be required."
    ],
    "cooldown": [
        "Why wait?",
        "Changing Board, Target, Firmware or Format can require several GitHub API requests to find current and historical images. Unauthenticated REST API access normally allows 60 requests per hour for a shared public IP, so computers on the same network may share that allowance.\n\nThe first three category changes in this app session do not require an app cooldown. Starting with change 4, every new category selection waits 60 seconds. A change during the wait restarts the 60 seconds for the new selection. The counter is not reset after waiting. Opening the app and refreshing the same selection do not count. 'No-wait changes left' is the app allowance, not GitHub requests remaining.\n\nAfter the countdown the final selection loads automatically. Local files remain available. This pause reduces request frequency; it cannot guarantee avoiding GitHub limits. A server-imposed wait can be longer.\n\nReference: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api"
    ],
    "firmware": [
        "Firmware, format and cable",
        "Target identifies the physical board/revision; Firmware selects its application. Choose the matching hardware and intended function. The FPGA chip ID alone cannot distinguish all supported boards.\n\nBIT loads the FPGA's working memory (SRAM) temporarily. It is lost when power is removed; the previous flash image is retained. MCS programs persistent flash for later startup. Both change the running application during programming.\n\nGitHub list downloads a selected revision; Local file uses a file already on your computer. The app validates contents, not just the extension. History limit is the number of image choices, not the number of network requests. Latest refers to the newest matching image name in the repository's default branch.\n\nThe cable is the USB/JTAG programmer, not the Ethernet adapter. With multiple cables, select the correct serial number; an FT232H ID alone does not prove the device is an HS3. Reading a list does not program a board. Program image starts programming after the existing checks."
    ],
    "ip": [
        "EEPROM IP and Current IP",
        "Target IP is the board's address used to contact it now. New device IP is the address you want to write; it is not your computer's address.\n\nEEPROM IP saves the address in nonvolatile memory for later startup. The address used now may stay unchanged until the device reloads its saved settings. EEPROM is memory that retains data without power.\n\nCurrent IP changes the running device's address without saving that change to EEPROM. It can be lost when the device restarts or reloads its settings. After a verified runtime write the app switches Target IP to the new address.\n\nThese choices apply when you press Write IP. Selecting a radio button alone changes nothing. Read IP reads settings without writing them. Plan for reconnecting at the new address and make sure it is not already used on your network."
    ],
    "target": [
        "Target IP and Ping",
        "Target IP is the board's current Ethernet address. SiTCP commonly defaults to 192.168.10.16; SiTCP-XG commonly defaults to 192.168.10.10. Your board may have a different saved or running address; use Custom when needed.\n\nPing checks for an ICMP response. No response does not prove the board is absent or that its register protocol is unavailable. Network settings on the computer must also permit reaching the board.\n\nget_version reads the common BCT firmware version register over RBCP and prints the FW ID, version and known firmware name in Messages. It does not write registers. Unknown firmware IDs are displayed without guessing the board type. A timeout or bus error is reported in Messages.\n\nNetwork controls communicate over Ethernet (RBCP register access). Firmware programming uses USB/JTAG instead and does not require temporary Ethernet settings."
    ],
    "host": [
        "Temporary host IP",
        "Host means this computer; Target means the board. NIC means the computer's Ethernet network adapter. Choose the adapter physically connected to the board.\n\nA temporary host IP such as 192.168.10.20 with mask 255.255.255.0 places the computer on the board's 192.168.10.x network. Use different, unused host and board addresses. The mask describes which addresses belong to the same local network.\n\nOn macOS, enabling the checkbox only reveals controls. Apply temporarily adds an address to the selected adapter after administrator approval, preserving DHCP, DNS and gateway settings. DHCP is automatic network configuration. Restore network or normal app exit removes the app's temporary address. Cleanup failures are reported.\n\nThis does not change the board's IP. It is optional for Ethernet operations and unnecessary for USB/JTAG firmware programming."
    ],
    "license": [
        "MPC / MPCX files",
        "MPC and MPCX are SiTCP/SiTCP-XG configuration or license files supplied for the intended device. They are not FPGA BIT/MCS firmware images. Use the file issued for your board; this app does not generate a license.\n\nChoose or paste a file path. Type is determined from the contents rather than its extension: MPC normally selects Target IP 192.168.10.16, MPCX selects 192.168.10.10. These are presets, not proof of your board's current address.\n\nRead retrieves device information. Check validates the selected data against the device without programming it. Write MPC/MPCX writes the selected data after confirmation. Initialize XG EEPROM copies current XG settings before license programming; leave it off unless this setup step is intended."
    ],
    "clock": [
        "Jitter Cleaner",
        "The CDCE62002 conditions the board's clock signal. Input frequency must match the clock supplied to the chip; output frequencies must match the intended board/firmware setup. MHz means millions of clock cycles per second.\n\nApply changes the running clock registers. With Save clock settings for the next power-on enabled, verified settings are also copied into the chip's nonvolatile EEPROM. Without it, the register changes are temporary. Selecting a frequency alone does not write anything.\n\nAn unsuitable clock can interrupt data acquisition or communication. Follow your experiment's clock plan; the app cannot infer the correct frequencies just from the network address. STAG clock writes remain unavailable until its register map is verified."
    ]
}


def show_help(parent, topic):
    from ui_language import HELP_JAPANESE

    root = parent.winfo_toplevel()
    manager = getattr(root, "ui_language", None)
    topics = HELP_JAPANESE if manager and manager.language == "ja" else HELP_TOPICS
    title, explanation = topics[topic]
    messagebox.showinfo(title, explanation, parent=root)


def help_link(parent, topic, text="Help"):
    link = ttk.Label(parent, text=text, foreground="#1769aa", cursor="hand2", takefocus=True)
    link.bind("<Button-1>", lambda unused: show_help(link, topic))
    link.bind("<Return>", lambda unused: show_help(link, topic))
    link.bind("<space>", lambda unused: show_help(link, topic))
    return link


def bind_horizontal_scroll(entry, explicit_navigation=False):
    def scroll(event):
        delta = getattr(event, "delta", 0)
        direction = -1 if delta > 0 or getattr(event, "num", None) == 4 else 1
        entry.xview_scroll(direction * max(1, abs(int(delta)) // 120), "units")
        return "break"

    for event in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>"):
        entry.bind(event, scroll)

    def reveal_cursor(event=None):
        entry.after_idle(lambda: entry.xview(entry.index("insert")))

    def navigate(event, key=None):
        key = key or event.keysym
        index = entry.index("insert")
        if key == "Home":
            index = 0
        elif key == "End":
            index = len(entry.get())
        else:
            index += -1 if key == "Left" else 1
        index = max(0, min(len(entry.get()), index))
        anchor = (
            entry.index("anchor")
            if entry.selection_present()
            else entry.index("insert")
        )
        entry.icursor(index)
        if event.state & 1:
            entry.selection_range(min(anchor, index), max(anchor, index))
        else:
            entry.selection_clear()
        entry.xview(index)
        return "break"

    entry.bind("<KeyRelease>", reveal_cursor, add="+")
    entry.bind("<ButtonRelease-1>", reveal_cursor, add="+")
    readonly = str(entry.cget("state")) == "readonly"
    if readonly or explicit_navigation:
        for key in ("Home", "End"):
            move = lambda event, key=key: navigate(event, key)
            entry.bind(f"<{key}>", move)
            entry.bind(f"<<Path{key}>>", move)
    if readonly:
        for event in ("<Left>", "<Right>"):
            entry.bind(event, navigate)


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

    def redraw():
        if not canvas.winfo_exists() or not canvas.winfo_ismapped():
            return
        canvas.itemconfigure(window, width=max(1, canvas.winfo_width()))
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.event_generate("<Expose>", when="tail")
        body.event_generate("<Expose>", when="tail")

    outer.refresh_content = redraw
    canvas.bind("<Map>", lambda unused: canvas.after_idle(redraw), add="+")
    outer.bind("<Map>", lambda unused: outer.after_idle(redraw), add="+")
    return outer, body


TARGET_IP_PRESETS = {
    "192.168.10.10 (SiTCP-XG default)": "192.168.10.10",
    "192.168.10.16 (SiTCP default)": "192.168.10.16",
}


class TargetAddress:
    def __init__(self, parent, task, events):
        self.task = task
        self.events = events
        self.choice = tk.StringVar(value="192.168.10.10 (SiTCP-XG default)")
        self.custom = tk.StringVar(value="192.168.10.10")
        box = ttk.Frame(parent)
        box.pack(fill="x", pady=6)
        ttk.Label(box, text="Target IP:").pack(side="left", padx=(0, 8))
        selector = ttk.Combobox(
            box,
            textvariable=self.choice,
            values=tuple(TARGET_IP_PRESETS) + ("Custom",),
            state="readonly",
            width=35,
        )
        selector.pack(side="left")
        self.entry = ttk.Entry(box, textvariable=self.custom, width=20)
        help_link(box, "target").pack(side="right", padx=4)
        self.ping_button = ttk.Button(box, text="Ping", command=self.ping)
        self.ping_button.pack(side="left", padx=8)
        self.ping_status = tk.StringVar()
        ttk.Label(box, textvariable=self.ping_status).pack(side="left", padx=(0, 8))
        self.version_button = ttk.Button(box, text="get_version", command=self.get_version)
        self.version_button.pack(side="left", padx=(0, 8))
        self.version_status = tk.StringVar()
        ttk.Label(box, textvariable=self.version_status).pack(side="left")
        self.choice.trace_add("write", lambda *unused: self.show_custom())
        self.custom.trace_add("write", lambda *unused: self.ping_status.set(""))
        self.custom.trace_add("write", lambda *unused: self.version_status.set(""))

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

    def get_version(self):
        try:
            host = self.value()
        except ValueError as error:
            self.version_status.set("Failed")
            self.events.put(("log", f"ERROR [get_version]: {error}"))
            return
        if self.version_button.instate(["disabled"]):
            return
        self.version_button.state(["disabled"])
        self.version_status.set("Reading...")

        def operation():
            try:
                output = operations.get_version(host)
                status = "Success"
            except Exception as error:
                output = f"ERROR [get_version {host}]: {error}"
                status = "Failed"
            self.events.put(("log", output))
            return "version_done", (self, host, status)

        self.task(f"get_version {id(self)} {host}", operation)

    def version_result(self, host, status):
        self.version_button.state(["!disabled"])
        try:
            current = self.value()
        except ValueError:
            current = ""
        self.version_status.set(status if current == host else "")

    def ping_result(self, host, status):
        self.ping_button.state(["!disabled"])
        try:
            current = self.value()
        except ValueError:
            current = ""
        self.ping_status.set(status if current == host else "")

    def show_custom(self):
        self.ping_status.set("")
        self.version_status.set("")
        if self.choice.get() == "Custom":
            self.entry.pack(side="left", padx=8, before=self.ping_button)
        else:
            self.entry.pack_forget()

    def value(self):
        return operations.ipv4(
            self.custom.get()
            if self.choice.get() == "Custom"
            else TARGET_IP_PRESETS[self.choice.get()]
        )

    def set(self, address):
        address = operations.ipv4(address)
        label = next(
            (label for label, value in TARGET_IP_PRESETS.items() if value == address),
            None,
        )
        if label:
            self.choice.set(label)
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
        notebook.add(clock_page, text="Jitter Cleaner")
        notebook.add(writer_page, text="MPC / MPCX")
        notebook.add(ip_page, text="IP addr.")
        file_box = ttk.Frame(self.writer)
        file_box.pack(fill="x", pady=(0, 6))
        ttk.Label(file_box, text="MPC / MPCX file:").pack(side="left", padx=(0, 8))
        self.file_entry = ttk.Entry(file_box, textvariable=self.file)
        self.file_entry.pack(side="left", fill="x", expand=True)
        bind_horizontal_scroll(self.file_entry, explicit_navigation=True)
        ttk.Button(file_box, text="Choose file", command=self.choose_file).pack(
            side="left", padx=6
        )
        help_link(file_box, "license").pack(side="left", padx=4)
        self.file_status = tk.StringVar(
            value="No file selected. Choose an MPC/MPCX file to detect its type."
        )
        ttk.Label(self.writer, textvariable=self.file_status, wraplength=900).pack(
            anchor="w"
        )
        self.file_validation = None
        self.detected_file = None
        self.file.trace_add("write", self.file_changed)
        self.file_entry.bind("<Return>", lambda unused: self.validate_file())
        self.file_entry.bind("<FocusOut>", lambda unused: self.validate_file())
        self.clock_target = TargetAddress(self.clock, task, events)
        self.writer_target = TargetAddress(self.writer, task, events)
        self.ip_target = TargetAddress(self.ip, task, events)
        for tab in (self.clock, self.writer, self.ip):
            network_widgets(tab)
        self.status_label = ttk.Label(
            self.clock, textvariable=self.status, wraplength=900
        )
        frequencies = ttk.Frame(self.clock)
        self.frequency_row = frequencies
        frequencies.pack(fill="x", pady=8)
        ttk.Label(
            frequencies,
            text="Select input / output frequencies of CDCE62002 chip (MHz):",
        ).pack(side="left", padx=(0, 8))
        ttk.Combobox(
            frequencies,
            textvariable=self.preset,
            values=tuple(operations.PRESETS),
            state="readonly",
            width=20,
        ).pack(side="left")
        help_link(frequencies, "clock").pack(side="left", padx=6)
        ttk.Checkbutton(
            self.clock,
            text="Save clock settings for the next power-on",
            variable=self.persist,
        ).pack(anchor="w")
        ttk.Button(
            self.clock,
            text="Apply",
            style="Action.TButton",
            command=self.configure_clock,
        ).pack(anchor="w", pady=10)
        ttk.Checkbutton(
            self.writer,
            text="Initialize XG EEPROM from current settings before license programming",
            variable=self.initialize,
        ).pack(anchor="w")
        ip_box = ttk.Frame(self.ip)
        ip_box.pack(fill="x", pady=8)
        ttk.Label(ip_box, text="New device IP:").pack(side="left", padx=(0, 8))
        ttk.Entry(ip_box, textvariable=self.new_ip, width=20).pack(side="left")
        help_link(ip_box, "ip").pack(side="right", padx=4)
        self.ip_mode_buttons = []
        for text, value in (("EEPROM IP", False), ("Current IP", True)):
            button = ttk.Radiobutton(
                ip_box, text=text, variable=self.current, value=value
            )
            button.pack(side="left", padx=8)
            self.ip_mode_buttons.append(button)
        actions = ttk.Frame(self.writer)
        actions.pack(fill="x", pady=10)
        for name in ("Read", "Check", "Write MPC/MPCX"):
            ttk.Button(
                actions,
                text=name,
                style="Action.TButton" if name == "Write MPC/MPCX" else "TButton",
                command=lambda action=name: self.utility(action),
            ).pack(side="left", padx=4)
        ip_actions = ttk.Frame(self.ip)
        ip_actions.pack(fill="x", pady=10)
        ttk.Button(
            ip_actions, text="Read IP", command=lambda: self.utility("Read IP")
        ).pack(side="left", padx=4)
        ttk.Button(
            ip_actions,
            text="Write IP",
            style="Action.TButton",
            command=lambda: self.utility("Write IP only"),
        ).pack(side="left", padx=4)
        board.trace_add("write", lambda *unused: self.refresh_board())
        self.refresh_board()

    def choose_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("MPC/MPCX", "*.mpc *.mpcx"), ("All files", "*")]
        )
        if not path:
            return
        self.file.set(path)
        self.validate_file()

    def selected_file(self):
        return (
            str(Path(self.file.get().strip().strip('"')).expanduser())
            if self.file.get().strip()
            else ""
        )

    def file_changed(self, *unused):
        if self.file_validation is not None:
            self.file_entry.after_cancel(self.file_validation)
        self.file_status.set(
            "Checking file..." if self.file.get().strip() else "No file selected."
        )
        self.file_validation = self.file_entry.after(400, self.validate_file)

    def validate_file(self):
        if self.file_validation is not None:
            self.file_entry.after_cancel(self.file_validation)
            self.file_validation = None
        try:
            path = self.selected_file()
            if not path:
                self.detected_file = None
                self.file_status.set("No file selected.")
                return False
            kind = operations.license_kind(path)
        except Exception as error:
            self.detected_file = None
            self.file_status.set(f"Invalid MPC/MPCX file: {error}")
            return False
        self.file_status.set(f"Detected from contents: {kind}")
        identity = (path, kind)
        if identity != self.detected_file:
            address = "192.168.10.10" if kind == "MPCX" else "192.168.10.16"
            self.writer_target.set(address)
            self.ip_target.set(address)
        self.detected_file = identity
        return True

    def refresh_board(self):
        if self.board.get() == "CIRASAME":
            self.preset.set("in_125_out_500_125")
        self.status.set(
            "STAG clock register map is not verified; clock writes are unavailable."
            if self.board.get() == "STAG"
            else ""
        )
        if self.status.get():
            self.status_label.pack(anchor="w", pady=8, before=self.frequency_row)
        else:
            self.status_label.pack_forget()

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
            selected_file = "" if ip_operation else self.selected_file()
            if not ip_operation and selected_file and action != "Read":
                if not self.validate_file():
                    raise ValueError(self.file_status.get())
            host = selected_target.value()
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
