#!/usr/bin/env python3
"""Desktop firmware, clock and SiTCP configuration with explicit hardware actions."""

import argparse
import ctypes as c
import importlib.util
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import uuid
import windows_usb as usb
import macos_network as network
from network_tabs import NetworkTabs
from desktop_services import DesktopServices, cable_arguments

ROOT = Path(__file__).resolve().parent


def app_data_directory():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AMANEQ"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AMANEQ"
    return (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "AMANEQ"
    )


def default_loader():
    relative = (
        "runtime/macos/bin/openFPGALoader"
        if sys.platform == "darwin"
        else "runtime/ucrt64/bin/openFPGALoader.exe"
    )
    candidate = ROOT / relative
    return str(candidate) if candidate.is_file() else "openFPGALoader"


def restore_cli_streams():
    # Windowed macOS bundles can start with None streams, even for a CLI child.
    for name, number in (("stdout", 1), ("stderr", 2)):
        if getattr(sys, name) is None:
            try:
                stream = os.fdopen(os.dup(number), "w", encoding="utf-8", buffering=1)
            except OSError:
                stream = open(os.devnull, "w", encoding="utf-8")
            setattr(sys, name, stream)


def configure_tls():
    certificate = ROOT / "runtime/cacert.pem"
    if certificate.is_file():
        os.environ.setdefault("SSL_CERT_FILE", str(certificate))


def command_prefix():
    return (
        [sys.executable]
        if getattr(sys, "frozen", False)
        else [sys.executable, str(Path(__file__).resolve())]
    )


def elevated(arguments):
    from ctypes import wintypes as w

    class ShellExecuteInfo(c.Structure):
        _fields_ = [
            ("cbSize", w.DWORD),
            ("fMask", w.ULONG),
            ("hwnd", w.HWND),
            ("lpVerb", w.LPCWSTR),
            ("lpFile", w.LPCWSTR),
            ("lpParameters", w.LPCWSTR),
            ("lpDirectory", w.LPCWSTR),
            ("nShow", c.c_int),
            ("hInstApp", w.HINSTANCE),
            ("lpIDList", c.c_void_p),
            ("lpClass", w.LPCWSTR),
            ("hkeyClass", w.HKEY),
            ("dwHotKey", w.DWORD),
            ("hIcon", w.HANDLE),
            ("hProcess", w.HANDLE),
        ]

    shell = c.WinDLL("shell32", use_last_error=True)
    kernel = c.WinDLL("kernel32", use_last_error=True)
    shell.ShellExecuteExW.argtypes = [c.POINTER(ShellExecuteInfo)]
    shell.ShellExecuteExW.restype = w.BOOL
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    kernel.GetExitCodeProcess.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    command = command_prefix() + arguments
    info = ShellExecuteInfo()
    info.cbSize = c.sizeof(info)
    info.fMask = 0x40  # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = command[0]
    info.lpParameters = subprocess.list2cmdline(command[1:])
    info.lpDirectory = str(ROOT)
    info.nShow = 0
    if not shell.ShellExecuteExW(c.byref(info)):
        raise usb.DriverError(
            f"Administrator approval failed or was cancelled (Windows error {c.get_last_error()})."
        )
    try:
        if kernel.WaitForSingleObject(info.hProcess, 0xFFFFFFFF) != 0:
            raise usb.DriverError(
                "Could not wait for the driver helper. Inspect driver status before retrying."
            )
        code = w.DWORD()
        if not kernel.GetExitCodeProcess(info.hProcess, c.byref(code)):
            raise c.WinError(c.get_last_error())
        return code.value
    finally:
        kernel.CloseHandle(info.hProcess)


def worker(action, serial, token):
    if (
        not token
        or len(token) != 32
        or any(ch not in "0123456789abcdef" for ch in token)
    ):
        raise usb.DriverError("Invalid driver operation token.")
    result = {"success": False, "action": action}
    try:
        result.update(usb.perform(action, serial, ROOT / "runtime" / "libwdi.dll"))
        result["success"] = True
    except Exception as error:
        result["error"] = str(error)
    usb.write_json(usb.state_root() / f"result-{token}.json", result)
    return 0 if result["success"] else 1


def firmware_cli(arguments):
    path = ROOT / "amaneq-firmware-programer.py"
    spec = importlib.util.spec_from_file_location("amaneq_core", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    # Downloads, readbacks and bridge caches must never modify a signed .app.
    module.ROOT = app_data_directory()
    sys.argv = [str(path)] + arguments
    try:
        return module.main()
    except (
        module.UserError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


def gui(smoke_test=False):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("AMANEQ Firmware Programer")
    root.geometry("1000x740")
    root.minsize(880, 680)
    events = queue.Queue()
    services = DesktopServices(ROOT, app_data_directory())
    found_cables, catalog_rows, adapters = [], [], []
    jobs = set()
    mutation = None
    lease = None
    closing = False
    serial = tk.StringVar()
    loader = tk.StringVar(value=default_loader())
    target = tk.StringVar(value="amaneq-v4")
    firmware = tk.StringVar(value="lrtdc")
    filename = tk.StringVar()
    confirmed_hs3 = tk.BooleanVar(value=False)
    cable_status = tk.StringVar(value="Scanning connected cables...")
    catalog_status = tk.StringVar(value="Loading latest firmware images...")
    adapter_label = tk.StringVar()
    address = tk.StringVar(value="192.168.10.20")
    mask = tk.StringVar(value="255.255.255.0")
    network_status = tk.StringVar(
        value="Choose Ethernet; temporary host IPv4 defaults to 192.168.10.20/24. DHCP is preserved."
    )
    outer = ttk.Frame(root, padding=10)
    outer.pack(fill="both", expand=True)
    board = tk.StringVar(value="AMANEQ")
    header = ttk.Frame(outer)
    header.pack(fill="x", pady=(0, 8))
    ttk.Label(header, text="Board").pack(side="left")
    ttk.Combobox(
        header,
        textvariable=board,
        values=("AMANEQ", "CIRASAME", "STAG"),
        state="readonly",
        width=18,
    ).pack(side="left", padx=8)
    board_status = tk.StringVar()
    ttk.Label(header, textvariable=board_status).pack(side="left")
    notebook = ttk.Notebook(outer)
    notebook.pack(fill="both", expand=True)
    page = ttk.Frame(notebook, padding=10)
    notebook.add(page, text="Firmware")
    adapter_boxes = []

    def task(name, function, changes=False, quiet=False):
        nonlocal mutation
        if closing or name in jobs or changes and mutation:
            if changes:
                messagebox.showinfo("Busy", "Wait for the current operation to finish.")
            return
        jobs.add(name)
        if changes:
            mutation = name

        def execute():
            try:
                result = function()
                if result:
                    events.put(result)
            except Exception as error:
                events.put(("error", (name, str(error), quiet)))
            finally:
                events.put(("done", name))

        threading.Thread(target=execute, daemon=True).start()

    def process(arguments):
        command = command_prefix() + ["--firmware-cli"] + arguments
        events.put(("log", subprocess.list2cmdline(command)))
        environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
        if os.name == "nt":
            environment["AMANEQ_CYGPATH_DIR"] = str(ROOT / "runtime/msys/bin")
        with subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=environment,
        ) as child:
            for line in child.stdout:
                events.put(("log", line.rstrip()))
            if child.wait():
                raise RuntimeError(
                    f"Programming stopped with exit {child.returncode}. See the log."
                )

    def scan(quiet=False):
        selected_loader = loader.get()
        task(
            "Cable scan",
            lambda: ("cables", services.scan(selected_loader)),
            quiet=quiet,
        )

    def refresh_catalog(force=True, quiet=False):
        task("Firmware list", lambda: ("catalog", services.catalog(force)), quiet=quiet)

    def show_catalog(*unused):
        if target.get() == "hrtdc-mezzanine":
            firmware.set("hrtdc")
        images.delete(*images.get_children())
        for index, row in enumerate(catalog_rows):
            if board.get() != "STAG" and row["target"] == target.get():
                version = services.core.version_key(row["path"])
                label = (
                    "v" + ".".join(format(part, "X") for part in version)
                    if version
                    else "default branch"
                )
                images.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(row["firmware"], row["format"].upper(), label, row["name"]),
                )

    def pick_image(unused=None):
        selection = images.selection()
        if selection:
            row = catalog_rows[int(selection[0])]
            firmware.set(row["firmware"])

    def program(source):
        if board.get() == "STAG":
            messagebox.showerror(
                "Firmware profile",
                "This board's FPGA and flash profile is not yet verified. AMANEQ images cannot be used. Network tabs remain available.",
            )
            return
        try:
            arguments = [
                "program",
                "--loader",
                loader.get(),
                "--target",
                target.get(),
                "--firmware",
                firmware.get(),
                "--yes",
            ]
            arguments += cable_arguments(
                serial.get(), found_cables, confirmed_hs3.get()
            )
            if source == "selected":
                selection = images.selection()
                if not selection:
                    raise ValueError(
                        "Select a firmware image from the latest-image list."
                    )
                row = catalog_rows[int(selection[0])]
                arguments = [
                    "program",
                    "--loader",
                    loader.get(),
                    "--target",
                    row["target"],
                    "--firmware",
                    row["firmware"],
                    "--yes",
                ] + cable_arguments(serial.get(), found_cables, confirmed_hs3.get())
                arguments += [
                    "--repo",
                    row["repo"],
                    "--ref",
                    row["commit"],
                    "--artifact-path",
                    row["path"],
                    "--format",
                    row["format"],
                ]
                if row["target"] == "hrtdc-mezzanine":
                    variant = next(
                        (
                            part
                            for part in ("mt25qu256", "n25q128")
                            if part in row["path"].lower()
                        ),
                        None,
                    )
                    if not variant:
                        raise ValueError(
                            "Use Program latest MCS (auto) to probe and select the mezzanine variant."
                        )
                    arguments += ["--flash", variant]
                description = row["name"] + "\nCommit: " + row["commit"][:12]
            elif source == "latest":
                arguments += ["--latest", "--format", "mcs"]
                description = f"Latest {target.get()} / {firmware.get()} MCS (resolved before download)"
            else:
                if not filename.get():
                    raise ValueError("Choose a local BIT/MCS file first.")
                arguments += ["--file", filename.get()]
                description = filename.get()
        except Exception as error:
            messagebox.showerror("Selection required", str(error))
            return
        if messagebox.askyesno(
            "Program firmware",
            f"Program cable serial {serial.get()}?\n{description}\n\nMCS changes persistent flash. BIT replaces the SRAM application.",
        ):
            task("Programming", lambda: process(arguments), changes=True)

    def driver(action):
        chosen = serial.get()
        selected_loader = loader.get()
        matches = [
            item
            for item in found_cables
            if item.get("vidpid", "").upper() == "0403:6014"
        ]
        if (
            len(matches) != 1
            or matches[0].get("serial") != chosen
            or not confirmed_hs3.get()
        ):
            messagebox.showerror(
                "USB selection",
                "Connect exactly one FT232H, select its serial, and confirm the physical HS3 model.",
            )
            return
        if not messagebox.askyesno(
            "USB driver change",
            f"{action} for HS3 serial {chosen}?\nClose Vivado and other cable applications.\nThe original driver is backed up before WinUSB installation. Hardware-ID matching can affect other FT232H devices when reconnected. Windows will request administrator approval.",
        ):
            return

        def operation():
            token = uuid.uuid4().hex
            code = elevated(
                ["--usb-worker", action, "--serial", chosen, "--operation-token", token]
            )
            report = usb.state_root() / f"result-{token}.json"
            if not report.exists():
                raise RuntimeError(
                    "No driver report found. Use the same Windows account for administrator approval and inspect the current driver."
                )
            result = json.loads(report.read_text(encoding="utf-8"))
            events.put(("log", json.dumps(result, indent=2)))
            if code or not result["success"]:
                raise RuntimeError(result.get("error", "Driver helper failed."))
            return "cables", services.scan(selected_loader)

        task("USB driver", operation, changes=True)

    def refresh_adapters(quiet=False):
        task(
            "Ethernet list",
            lambda: ("adapters", network.ethernet_adapters()),
            quiet=quiet,
        )

    def apply_network():
        nonlocal lease
        if lease or mutation:
            messagebox.showinfo(
                "Temporary network",
                "Restore the active temporary address or wait for the current operation first.",
            )
            return
        selected = [
            item
            for item in adapters
            if f"{item['name']} ({item['interface']})" == adapter_label.get()
        ]
        if len(selected) != 1:
            messagebox.showerror(
                "Ethernet", "Select an Ethernet adapter from the list."
            )
            return
        interface, chosen_ip, chosen_mask = (
            selected[0]["interface"],
            address.get().strip(),
            mask.get().strip(),
        )
        try:
            network.validate_configuration(interface, chosen_ip, chosen_mask, [])
        except Exception as error:
            messagebox.showerror("IPv4 settings", str(error))
            return
        if not messagebox.askyesno(
            "Temporary IPv4",
            f"Add {chosen_ip} / {chosen_mask} to {adapter_label.get()}?\nExisting DHCP, DNS and gateway settings are preserved.\nOnly this alias will be removed on restore or application exit. macOS will request administrator approval.",
        ):
            return

        def operation():
            path, data = network.create_lease(
                app_data_directory(), interface, chosen_ip, chosen_mask
            )
            events.put(("lease", (path, data)))
            try:
                result = network.authorize("apply", path, command_prefix())
                return (
                    "network",
                    f"Temporary {data['address']} on {interface}. Auto-cleanup active.",
                )
            except Exception:
                signal = json.loads(path.read_text(encoding="utf-8"))
                signal["release"] = True
                network.save(path, signal)
                raise

        task("Temporary IPv4", operation, changes=True)

    def restore_network(exit_after=False):
        if not lease:
            if exit_after:
                root.destroy()
            return
        path, data = lease

        def operation():
            network.release(path, data, command_prefix())
            return "released", exit_after

        task("Restore IPv4", operation, changes=True)

    cable_box = ttk.LabelFrame(page, text="Connected cable", padding=8)
    cable_box.pack(fill="x")
    cable = ttk.Combobox(cable_box, textvariable=serial, state="readonly", width=28)
    cable.grid(row=0, column=0, sticky="ew")
    ttk.Button(cable_box, text="Rescan cables", command=scan).grid(
        row=0, column=1, padx=6
    )
    ttk.Checkbutton(
        cable_box,
        variable=confirmed_hs3,
        text="My cable is an HS3 (confirm if model is unknown)",
    ).grid(row=0, column=2, sticky="w")
    ttk.Label(cable_box, textvariable=cable_status, wraplength=900).grid(
        row=1, column=0, columnspan=3, sticky="w"
    )
    settings = ttk.Frame(page)
    settings.pack(fill="x", pady=8)
    ttk.Label(settings, text="Target").grid(row=0, column=0)
    target_box = ttk.Combobox(
        settings,
        textvariable=target,
        state="readonly",
        values=("amaneq-v1", "amaneq-v4", "hrtdc-mezzanine"),
        width=21,
    )
    target_box.grid(row=0, column=1, padx=6)
    target_box.bind("<<ComboboxSelected>>", show_catalog)
    ttk.Label(settings, text="Firmware").grid(row=0, column=2)
    firmware_box = ttk.Combobox(
        settings,
        textvariable=firmware,
        state="readonly",
        values=("lrtdc", "hrtdc", "lrtdc-10g", "mikumari", "skeleton"),
        width=15,
    )
    firmware_box.grid(row=0, column=3, padx=6)
    ttk.Label(settings, text="Loader").grid(row=1, column=0)
    ttk.Entry(settings, textvariable=loader, width=62).grid(
        row=1, column=1, columnspan=3, sticky="ew", pady=4
    )
    ttk.Button(
        settings,
        text="Browse",
        command=lambda: loader.set(filedialog.askopenfilename() or loader.get()),
    ).grid(row=1, column=4)
    ttk.Label(page, textvariable=catalog_status, wraplength=950).pack(anchor="w")
    table_frame = ttk.Frame(page)
    table_frame.pack(fill="both", expand=True, pady=4)
    images = ttk.Treeview(
        table_frame,
        columns=("family", "format", "version", "file"),
        show="headings",
        height=7,
        selectmode="browse",
    )
    for name, title, width in [
        ("family", "Firmware", 110),
        ("format", "Type", 55),
        ("version", "Version", 95),
        ("file", "Latest filename", 580),
    ]:
        images.heading(name, text=title)
        images.column(name, width=width, stretch=name == "file")
    images.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=images.yview)
    scrollbar.pack(side="right", fill="y")
    images.configure(yscrollcommand=scrollbar.set)
    images.bind("<<TreeviewSelect>>", pick_image)
    buttons = ttk.Frame(page)
    buttons.pack(fill="x", pady=4)
    for title, callback in [
        ("Program selected image", lambda: program("selected")),
        ("Program latest MCS (auto)", lambda: program("latest")),
        ("Refresh image list", refresh_catalog),
    ]:
        ttk.Button(buttons, text=title, command=callback).pack(side="left", padx=(0, 6))
    local = ttk.Frame(page)
    local.pack(fill="x", pady=4)
    ttk.Entry(local, textvariable=filename).pack(side="left", fill="x", expand=True)
    ttk.Button(
        local,
        text="Local file",
        command=lambda: filename.set(filedialog.askopenfilename() or filename.get()),
    ).pack(side="left", padx=6)
    ttk.Button(local, text="Program local file", command=lambda: program("local")).pack(
        side="left"
    )
    if os.name == "nt":
        controls = ttk.Frame(page)
        controls.pack(fill="x", pady=4)
        ttk.Button(controls, text="Use WinUSB", command=lambda: driver("winusb")).pack(
            side="left", padx=4
        )
        ttk.Button(
            controls, text="Restore Vivado driver", command=lambda: driver("restore")
        ).pack(side="left", padx=4)

    def network_widgets(parent):
        if sys.platform != "darwin":
            ttk.Label(
                parent,
                text="Temporary IP automation is available on macOS. On Linux/WSL configure the host Ethernet to 192.168.10.20/24 before using network operations.",
                wraplength=900,
            ).pack(anchor="w", pady=8)
            return
        net = ttk.LabelFrame(
            parent,
            text="Temporary host IPv4 (preserves DHCP; restored on exit)",
            padding=8,
        )
        net.pack(fill="x", pady=6)
        adapter_box = ttk.Combobox(
            net, textvariable=adapter_label, state="readonly", width=28
        )
        adapter_box.grid(row=0, column=0, sticky="ew")
        adapter_boxes.append(adapter_box)
        ttk.Button(net, text="Refresh", command=refresh_adapters).grid(
            row=0, column=1, padx=4
        )
        ttk.Label(net, text="IP").grid(row=0, column=2)
        ttk.Entry(net, textvariable=address, width=16).grid(row=0, column=3)
        ttk.Label(net, text="Mask").grid(row=0, column=4)
        ttk.Entry(net, textvariable=mask, width=16).grid(row=0, column=5)
        ttk.Button(net, text="Apply temporarily", command=apply_network).grid(
            row=1, column=0, pady=4
        )
        ttk.Button(net, text="Restore network", command=restore_network).grid(
            row=1, column=1, columnspan=2
        )
        ttk.Label(net, textvariable=network_status, wraplength=900).grid(
            row=2, column=0, columnspan=6, sticky="w"
        )

    network_tabs = NetworkTabs(notebook, board, ROOT, task, events, network_widgets)

    def board_changed(*unused):
        chosen = board.get()
        if chosen == "CIRASAME":
            target_box["values"] = ("cirasame",)
            target.set("cirasame")
            firmware_box["values"] = ("lrtdc", "lrtdc-10g", "skeleton")
            if firmware.get() not in firmware_box["values"]:
                firmware.set("lrtdc")
        elif chosen == "AMANEQ":
            target_box["values"] = ("amaneq-v1", "amaneq-v4", "hrtdc-mezzanine")
            if target.get() not in target_box["values"]:
                target.set("amaneq-v4")
            firmware_box["values"] = (
                "lrtdc",
                "hrtdc",
                "lrtdc-10g",
                "mikumari",
                "skeleton",
            )
        board_status.set(
            "STAG firmware and clock maps require an official reference."
            if chosen == "STAG"
            else ""
        )
        show_catalog()

    board.trace_add("write", board_changed)
    board_changed()
    log = tk.Text(outer, height=6, wrap="word")
    log.pack(fill="both", expand=True, pady=(4, 0))

    def poll():
        nonlocal mutation, found_cables, catalog_rows, adapters, lease, closing
        while not events.empty():
            kind, value = events.get_nowait()
            if kind == "done":
                jobs.discard(value)
                if mutation == value:
                    mutation = None
            elif kind == "cables":
                found_cables = value
                values = [item.get("serial") for item in value if item.get("serial")]
                cable["values"] = values
                if len(value) == 1 and len(values) == 1:
                    serial.set(values[0])
                elif serial.get() not in values or len(values) != len(set(values)):
                    serial.set("")
                description = "; ".join(
                    f"{item.get('serial') or '<not reported>'}: {item.get('type')} / {item.get('driver')}"
                    for item in value
                )
                cable_status.set(
                    description
                    or "No cable found. Connect the cable and press Rescan cables."
                )
                if len(value) > 1:
                    cable_status.set(
                        "Multiple cables: explicitly select a serial. " + description
                    )
            elif kind == "catalog":
                catalog_rows, status, failures = value
                catalog_status.set(status)
                show_catalog()
                if failures:
                    log.insert("end", "\n".join(failures) + "\n")
            elif kind == "adapters":
                adapters = value
                labels = [f"{item['name']} ({item['interface']})" for item in value]
                for adapter_box in adapter_boxes:
                    adapter_box["values"] = labels
                if adapter_label.get() not in labels:
                    adapter_label.set("")
            elif kind == "endpoint":
                network_tabs.mode.set("Custom")
                network_tabs.custom.set(value)
            elif kind == "lease":
                lease = value
            elif kind == "network":
                network_status.set(value)
            elif kind == "released":
                lease = None
                network_status.set(
                    "Temporary IPv4 removed. Original DHCP/DNS/gateway settings were preserved."
                )
                if value:
                    root.destroy()
                    return
            elif kind == "error":
                name, text, quiet = value
                log.insert("end", f"ERROR [{name}]: {text}\n")
                if name == "Cable scan":
                    cable_status.set("Cable scan failed. " + text)
                elif name == "Firmware list":
                    catalog_status.set("Firmware list unavailable. " + text)
                elif "IPv4" in name:
                    network_status.set(
                        "Network operation failed; inspect the log and use Restore network."
                    )
                    closing = False
                if not quiet:
                    messagebox.showerror(name, text)
            elif kind == "log":
                log.insert("end", value + "\n")
            log.see("end")
        root.after(100, poll)

    def close():
        nonlocal closing
        if mutation:
            messagebox.showinfo(
                "Operation running",
                "Wait for programming or the system operation to finish.",
            )
        elif lease:
            # Start cleanup before marking the UI closed; task() rejects closed work.
            restore_network(exit_after=True)
            closing = True
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    poll()
    if smoke_test:
        assert len(notebook.tabs()) == 3
        board.set("CIRASAME")
        assert target.get() == "cirasame"
        assert network_tabs.preset.get() == "in_125_out_500_125"
        board.set("STAG")
        assert "official reference" in board_status.get()
        board.set("AMANEQ")
        assert target.get() == "amaneq-v4"
        for mode, expected in (("MPC", "192.168.10.16"), ("MPCX", "192.168.10.10")):
            network_tabs.mode.set(mode)
            assert network_tabs.custom.get() == expected
        for tab in notebook.tabs():
            notebook.select(tab)
            root.update_idletasks()
        notebook.select(0)
        root.after(300, root.destroy)
    else:
        root.after(50, lambda: scan(quiet=True))
        root.after(75, lambda: refresh_catalog(force=False, quiet=True))
        if sys.platform == "darwin":
            root.after(100, lambda: refresh_adapters(quiet=True))
    root.mainloop()


def main():
    configure_tls()
    if len(sys.argv) > 1 and sys.argv[1] == "--firmware-cli":
        restore_cli_streams()
        return firmware_cli(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--usb-worker", choices=("winusb", "restore"), help=argparse.SUPPRESS
    )
    parser.add_argument("--serial", help=argparse.SUPPRESS)
    parser.add_argument("--operation-token", help=argparse.SUPPRESS)
    parser.add_argument(
        "--network-worker", choices=("apply", "remove", "guard"), help=argparse.SUPPRESS
    )
    parser.add_argument("--lease", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Build and close the desktop window without hardware/network operations",
    )
    args = parser.parse_args()
    if args.usb_worker:
        return worker(args.usb_worker, args.serial, args.operation_token)
    if args.network_worker:
        restore_cli_streams()
        try:
            result = network.privileged(
                args.network_worker, args.lease, command_prefix()
            )
            print(json.dumps(result))
            return 0
        except Exception as error:
            print(str(error), file=sys.stderr)
            return 1
    if getattr(sys, "frozen", False) and os.name == "nt":
        kernel = c.WinDLL("kernel32")
        kernel.GetConsoleWindow.restype = c.c_void_p
        user = c.WinDLL("user32")
        user.ShowWindow.argtypes = [c.c_void_p, c.c_int]
        user.ShowWindow(kernel.GetConsoleWindow(), 0)
    gui(args.smoke_test)
    return 0


if __name__ == "__main__":
    sys.exit(main())
