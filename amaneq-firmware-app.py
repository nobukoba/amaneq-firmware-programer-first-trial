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
from network_tabs import NetworkTabs, bind_horizontal_scroll
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
    root.minsize(720, 480)
    root.resizable(True, True)
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
    firmware_labels = {
        "lrtdc": "LR-TDC",
        "hrtdc": "HR-TDC",
        "lrtdc-10g": "LR-TDC 10GbE",
        "mikumari": "MIKUMARI Hub",
        "skeleton": "Skelton",
    }
    firmware_ids = {label: key for key, label in firmware_labels.items()}
    firmware = tk.StringVar(value="lrtdc")
    firmware_display = tk.StringVar(value=firmware_labels[firmware.get()])
    format_labels = {"mcs": ".mcs file", "bit": ".bit file"}
    format_ids = {label: key for key, label in format_labels.items()}
    image_format = tk.StringVar(value=format_labels["mcs"])
    filename = tk.StringVar()
    source_mode = tk.StringVar(value="GitHub")
    history_limit = tk.StringVar(value="10")
    repository_url = tk.StringVar()
    repository_overrides = {}
    active_profile = None
    catalog_request = 0
    refresh_after = None
    changing_repository = False
    last_cable_serial = None
    temporary_enabled = tk.BooleanVar(value=False)
    temporary_panels = []
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
    split = ttk.Panedwindow(outer, orient="vertical")
    split.pack(fill="both", expand=True)
    notebook = ttk.Notebook(split)
    split.add(notebook, weight=3)
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
        nonlocal catalog_request
        catalog_request += 1
        request = catalog_request
        images.delete(*images.get_children())
        if source_mode.get() != "GitHub" or board.get() == "STAG":
            return
        chosen_repository = repository_url.get().strip()
        chosen_target, chosen_firmware = target.get(), firmware.get()
        chosen_format = format_ids[image_format.get()]
        try:
            chosen_limit = int(history_limit.get())
            if not 1 <= chosen_limit <= 1000:
                raise ValueError()
        except ValueError:
            catalog_status.set("History limit must be an integer between 1 and 1000.")
            return
        catalog_status.set("Loading matching firmware images...")

        def operation():
            result = services.image_list(
                chosen_repository,
                chosen_target,
                chosen_firmware,
                force,
                include_history=True,
                history_limit=chosen_limit,
                image_format=chosen_format,
            )
            return "catalog", (request, result)

        task(f"Firmware list #{request}", operation, quiet=quiet)

    def show_catalog(*unused):
        images.delete(*images.get_children())
        if board.get() == "STAG":
            return
        for index, row in enumerate(catalog_rows):
            if (
                row["target"] == target.get()
                and row["firmware"] == firmware.get()
                and row["format"] == format_ids[image_format.get()]
            ):
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
                    values=(
                        format_labels[row["format"]],
                        label,
                        row["name"],
                        row.get("revision", ""),
                    ),
                )
        visible = images.get_children()
        if visible:
            images.selection_set(visible[0])
            images.focus(visible[0])
            images.see(visible[0])

    def schedule_refresh(*unused):
        nonlocal refresh_after, catalog_request
        if changing_repository:
            return
        catalog_request += 1
        images.delete(*images.get_children())
        if active_profile:
            repository_overrides[active_profile] = repository_url.get()
        if refresh_after:
            root.after_cancel(refresh_after)
        catalog_status.set("Repository changed. Loading matching images...")
        if not smoke_test:
            refresh_after = root.after(
                600, lambda: refresh_catalog(force=False, quiet=True)
            )

    def set_firmware_choices(keys):
        firmware_box["values"] = tuple(firmware_labels[key] for key in keys)

    def firmware_picked(unused=None):
        firmware.set(firmware_ids[firmware_display.get()])
        profile_changed()

    def profile_changed(*unused):
        nonlocal active_profile, changing_repository, catalog_request
        catalog_request += 1
        if target.get() == "hrtdc-mezzanine":
            firmware.set("hrtdc")
            set_firmware_choices(("hrtdc",))
            firmware_label.grid_remove()
            firmware_box.grid_remove()
        else:
            firmware_label.grid()
            firmware_box.grid()
        if target.get() != "hrtdc-mezzanine" and board.get() == "AMANEQ":
            set_firmware_choices(
                (
                    "lrtdc",
                    "hrtdc",
                    "lrtdc-10g",
                    "mikumari",
                    "skeleton",
                )
            )
        firmware_display.set(firmware_labels[firmware.get()])
        format_box["values"] = tuple(format_labels.values())
        if image_format.get() not in format_box["values"]:
            image_format.set(format_labels["mcs"])
        active_profile = (target.get(), firmware.get())
        if board.get() == "STAG":
            show_catalog()
            return
        changing_repository = True
        repository_url.set(
            repository_overrides.get(
                active_profile,
                "https://github.com/" + services.default_repository(*active_profile),
            )
        )
        changing_repository = False
        refresh_catalog(force=False, quiet=True) if not smoke_test else show_catalog()

    def change_source(*unused):
        nonlocal catalog_request
        catalog_request += 1
        online.pack_forget()
        local.pack_forget()
        if source_mode.get() == "GitHub":
            online.pack(fill="both", expand=True, before=program_area)
            if not smoke_test:
                refresh_catalog(force=False, quiet=True)
        else:
            local.pack(fill="x", pady=12, before=program_area)

    def program():
        source = "selected" if source_mode.get() == "GitHub" else "local"
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
                expected_repo = services.core.GitHub(repository_url.get().strip()).repo
                if (
                    row["repo"] != expected_repo
                    or row["target"] != target.get()
                    or row["firmware"] != firmware.get()
                    or row["format"] != format_ids[image_format.get()]
                ):
                    raise ValueError(
                        "The image list is stale. Refresh the selected repository/profile first."
                    )
                if row["target"] == "hrtdc-mezzanine":
                    variant = next(
                        (
                            part
                            for part in ("mt25qu256", "n25q128")
                            if part in row["path"].lower()
                        ),
                        None,
                    )
                    if variant:
                        arguments += ["--flash", variant]
                description = row["name"] + "\nCommit: " + row["commit"][:12]
            else:
                if not filename.get():
                    raise ValueError("Choose a local .bit file or .mcs file first.")
                arguments += [
                    "--file",
                    filename.get(),
                    "--format",
                    format_ids[image_format.get()],
                ]
                description = filename.get()
        except Exception as error:
            messagebox.showerror("Selection required", str(error))
            return
        chosen_format = format_ids[image_format.get()]
        chosen_local_file = filename.get()

        def operation():
            if source == "local":
                detected = services.core.inspect_file(Path(chosen_local_file))
                if detected.kind != chosen_format:
                    raise ValueError(
                        "Local image contents do not match the selected .mcs file / .bit file format."
                    )
            return process(arguments)

        if messagebox.askyesno(
            "Program firmware",
            f"Program cable serial {serial.get()}?\n{description}\n\nA .mcs file changes persistent flash. A .bit file replaces the SRAM application.",
        ):
            task("Programming", operation, changes=True)

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

    cable_box = ttk.LabelFrame(page, text="Cable (automatically detected)", padding=8)
    cable_box.pack(fill="x")
    cable = ttk.Combobox(cable_box, textvariable=serial, state="readonly", width=28)
    cable.grid(row=0, column=0, sticky="ew")
    cable.bind("<<ComboboxSelected>>", lambda unused: update_cable_model())
    ttk.Button(cable_box, text="Rescan", command=scan).grid(row=0, column=1, padx=6)
    hs3_confirmation = ttk.Checkbutton(
        cable_box,
        variable=confirmed_hs3,
        text="The unidentified FT232H cable is physically an HS3",
    )
    hs3_confirmation.grid(row=0, column=2, sticky="w")
    hs3_confirmation.grid_remove()
    ttk.Label(cable_box, textvariable=cable_status, wraplength=900).grid(
        row=1, column=0, columnspan=3, sticky="w"
    )

    def update_cable_model():
        nonlocal last_cable_serial
        if serial.get() != last_cable_serial:
            confirmed_hs3.set(False)
            last_cable_serial = serial.get()
        matches = [item for item in found_cables if item.get("serial") == serial.get()]
        if (
            len(matches) == 1
            and matches[0].get("vidpid", "").upper() == "0403:6014"
            and not matches[0].get("cable")
        ):
            hs3_confirmation.grid()
        else:
            hs3_confirmation.grid_remove()

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
    target_box.bind("<<ComboboxSelected>>", profile_changed)
    firmware_label = ttk.Label(settings, text="Firmware")
    firmware_label.grid(row=0, column=2)
    firmware_box = ttk.Combobox(
        settings,
        textvariable=firmware_display,
        state="readonly",
        values=tuple(firmware_labels.values()),
        width=18,
    )
    firmware_box.grid(row=0, column=3, padx=6)
    firmware_box.bind("<<ComboboxSelected>>", firmware_picked)
    ttk.Label(settings, text="Format").grid(row=0, column=4, padx=(10, 0))
    format_box = ttk.Combobox(
        settings,
        textvariable=image_format,
        state="readonly",
        values=tuple(format_labels.values()),
        width=11,
    )
    format_box.grid(row=0, column=5, padx=6)
    format_box.bind(
        "<<ComboboxSelected>>", lambda unused: refresh_catalog(force=False, quiet=True)
    )
    source_controls = ttk.Frame(page)
    source_controls.pack(fill="x", pady=4)
    ttk.Label(source_controls, text="Image source").pack(side="left", padx=(0, 12))
    for value, text in (("GitHub", "GitHub list"), ("Local", "Local file")):
        ttk.Radiobutton(
            source_controls,
            text=text,
            value=value,
            variable=source_mode,
            command=change_source,
        ).pack(side="left", padx=8)
    online = ttk.Frame(page)
    online.pack(fill="both", expand=True)
    repository_box = ttk.Frame(online)
    repository_box.pack(fill="x", pady=4)
    ttk.Label(repository_box, text="GitHub URL").pack(side="left", padx=(0, 8))
    repository_entry = ttk.Entry(repository_box, textvariable=repository_url)
    repository_entry.pack(side="left", fill="x", expand=True)
    bind_horizontal_scroll(repository_entry)
    repository_entry.bind("<Return>", lambda unused: refresh_catalog())
    ttk.Button(repository_box, text="Refresh list", command=refresh_catalog).pack(
        side="left", padx=6
    )
    history_controls = ttk.Frame(online)
    history_controls.pack(fill="x", pady=4)
    ttk.Label(history_controls, text="History limit").pack(side="left")
    history_box = ttk.Spinbox(
        history_controls,
        from_=1,
        to=1000,
        textvariable=history_limit,
        width=7,
        command=lambda: refresh_catalog(force=False, quiet=True),
    )
    history_box.pack(side="left", padx=8)
    history_box.bind(
        "<Return>", lambda unused: refresh_catalog(force=False, quiet=True)
    )
    ttk.Label(
        history_controls, text="Default 10 images; includes tags and firmware commits"
    ).pack(side="left")
    ttk.Label(online, textvariable=catalog_status, wraplength=930).pack(anchor="w")
    table_frame = ttk.Frame(online)
    table_frame.pack(fill="both", expand=True, pady=4)
    images = ttk.Treeview(
        table_frame,
        columns=("format", "version", "file", "revision"),
        show="headings",
        height=7,
        selectmode="browse",
    )
    for name, title, width in (
        ("format", "Type", 90),
        ("version", "Version", 95),
        ("file", "Firmware image", 490),
        ("revision", "Tag / commit", 235),
    ):
        images.heading(name, text=title)
        images.column(name, width=width, stretch=name == "file")
    images.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=images.yview)
    scrollbar.pack(side="right", fill="y")
    images.configure(yscrollcommand=scrollbar.set)
    local = ttk.LabelFrame(page, text="Local .bit file / .mcs file", padding=12)
    local_entry = ttk.Entry(local, textvariable=filename, state="readonly")
    local_entry.pack(side="left", fill="x", expand=True)
    bind_horizontal_scroll(local_entry)
    ttk.Button(
        local,
        text="Choose file",
        command=lambda: filename.set(
            filedialog.askopenfilename(
                filetypes=[("Firmware", "*.mcs *.bit"), ("All files", "*")]
            )
            or filename.get()
        ),
    ).pack(side="left", padx=8)
    program_area = ttk.Frame(page)
    program_area.pack(fill="x", pady=10)
    from tkinter import font as tkfont

    style = ttk.Style(root)
    action_font = tkfont.Font(
        root=root, font=style.lookup("TButton", "font") or "TkDefaultFont"
    )
    action_font.configure(weight="bold")
    style.configure("Action.TButton", font=action_font)
    ttk.Button(
        program_area, text="Program image", style="Action.TButton", command=program
    ).pack(anchor="w")
    repository_url.trace_add("write", schedule_refresh)
    if os.name == "nt":
        controls = ttk.Frame(page)
        controls.pack(fill="x", pady=4)
        ttk.Button(controls, text="Use WinUSB", command=lambda: driver("winusb")).pack(
            side="left", padx=4
        )
        ttk.Button(
            controls, text="Restore Vivado driver", command=lambda: driver("restore")
        ).pack(side="left", padx=4)

    def toggle_temporary():
        if not temporary_enabled.get() and mutation in (
            "Temporary IPv4",
            "Restore IPv4",
        ):
            temporary_enabled.set(True)
            return
        if not temporary_enabled.get() and lease:
            temporary_enabled.set(True)
            restore_network()
            return
        for panel in temporary_panels:
            if temporary_enabled.get():
                panel.pack(fill="x")
            else:
                panel.pack_forget()

    def network_widgets(parent):
        holder = ttk.Frame(parent)
        holder.pack(fill="x", pady=4)
        ttk.Checkbutton(
            holder,
            text="Temporary static host IP address (DHCP preserved, restored on exit)",
            variable=temporary_enabled,
            command=toggle_temporary,
        ).pack(anchor="w")
        panel = ttk.Frame(holder)
        temporary_panels.append(panel)
        if sys.platform != "darwin":
            ttk.Label(
                panel,
                text="Temporary IP automation is available on macOS. On Linux/WSL configure the host Ethernet to 192.168.10.20/24 before using network operations.",
                wraplength=900,
            ).pack(anchor="w", pady=8)
            return
        net = ttk.Frame(panel, padding=8)
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
            set_firmware_choices(("lrtdc", "lrtdc-10g", "skeleton"))
            if firmware.get() not in ("lrtdc", "lrtdc-10g", "skeleton"):
                firmware.set("lrtdc")
        elif chosen == "AMANEQ":
            target_box["values"] = ("amaneq-v1", "amaneq-v4", "hrtdc-mezzanine")
            if target.get() not in target_box["values"]:
                target.set("amaneq-v4")
            set_firmware_choices(
                (
                    "lrtdc",
                    "hrtdc",
                    "lrtdc-10g",
                    "mikumari",
                    "skeleton",
                )
            )
        board_status.set(
            "STAG firmware and clock maps require an official reference."
            if chosen == "STAG"
            else ""
        )
        profile_changed()

    board.trace_add("write", board_changed)
    board_changed()
    messages = ttk.Frame(split, padding=(0, 4))
    split.add(messages, weight=1)
    message_controls = ttk.Frame(messages)
    message_controls.pack(fill="x")
    ttk.Label(message_controls, text="Messages").pack(side="left")
    follow_messages = tk.BooleanVar(value=True)
    follow_box = ttk.Checkbutton(
        message_controls,
        text="Follow latest",
        variable=follow_messages,
        command=lambda: log.see("end") if follow_messages.get() else None,
    )
    follow_box.pack(side="left", padx=10)
    log_body = ttk.Frame(messages)
    log_body.pack(fill="both", expand=True)
    log = tk.Text(log_body, height=6, wrap="word")
    log_scrollbar = ttk.Scrollbar(log_body, orient="vertical")
    log_scrollbar.pack(side="right", fill="y")
    log.pack(side="left", fill="both", expand=True)
    log.configure(yscrollcommand=log_scrollbar.set)

    def scroll_messages(*arguments):
        follow_messages.set(False)
        log.yview(*arguments)

    log_scrollbar.configure(command=scroll_messages)
    for event in (
        "<MouseWheel>",
        "<Button-4>",
        "<Button-5>",
        "<Prior>",
        "<Home>",
        "<Up>",
    ):
        log.bind(event, lambda unused: follow_messages.set(False), add="+")

    def latest_messages():
        follow_messages.set(True)
        log.see("end")

    def first_messages():
        follow_messages.set(False)
        log.yview_moveto(0)

    ttk.Button(message_controls, text="First", command=first_messages).pack(
        side="left", padx=3
    )
    ttk.Button(message_controls, text="Latest", command=latest_messages).pack(
        side="left", padx=3
    )

    def redraw_selected():
        if not root.winfo_exists():
            return
        root.update_idletasks()
        selected = root.nametowidget(notebook.select())
        refresh = getattr(selected, "refresh_content", None)
        if refresh:
            refresh()
        selected.event_generate("<Expose>", when="tail")
        notebook.event_generate("<Expose>", when="tail")

    def tab_changed(unused=None):
        root.after_idle(redraw_selected)
        root.after(25, redraw_selected)

    notebook.bind("<<NotebookTabChanged>>", tab_changed, add="+")

    zoom = tk.StringVar(value="100%")
    zoom_controls = ttk.Frame(header)
    zoom_controls.pack(side="right")
    ttk.Label(zoom_controls, text="UI size").pack(side="left", padx=5)
    zoom_box = ttk.Combobox(
        zoom_controls,
        textvariable=zoom,
        values=("75%", "90%", "100%", "110%", "125%", "150%"),
        width=6,
        state="readonly",
    )
    zoom_box.pack(side="left")
    fonts = {
        name: tkfont.nametofont(name)
        for name in tkfont.names(root)
        if name.startswith("Tk")
    }
    fonts[str(action_font)] = action_font
    base_sizes = {name: font.cget("size") for name, font in fonts.items()}

    def resize_ui(unused=None):
        scale = int(zoom.get().removesuffix("%")) / 100
        for name, font in fonts.items():
            original = base_sizes[name]
            font.configure(
                size=max(1, round(abs(original) * scale)) * (-1 if original < 0 else 1)
            )
        style.configure(
            "Treeview",
            rowheight=tkfont.nametofont("TkDefaultFont").metrics("linespace") + 6,
        )
        redraw_selected()

    zoom_box.bind("<<ComboboxSelected>>", resize_ui)
    root.after_idle(lambda: split.sashpos(0, max(200, split.winfo_height() - 160)))

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
                update_cable_model()
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
                request, result = value
                if request != catalog_request or source_mode.get() != "GitHub":
                    continue
                catalog_rows, status, failures = result
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
            elif kind == "ping":
                field, host, status = value
                field.ping_result(host, status)
            elif kind == "endpoint":
                network_tabs.ip_target.set(value)
            elif kind == "lease":
                lease = value
            elif kind == "network":
                network_status.set(value)
            elif kind == "released":
                lease = None
                temporary_enabled.set(False)
                toggle_temporary()
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
                elif name.startswith("Firmware list #"):
                    if name != f"Firmware list #{catalog_request}":
                        continue
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
            if follow_messages.get():
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
        assert [notebook.tab(tab, "text") for tab in notebook.tabs()] == [
            "Firmware",
            "Jitter Cleaner",
            "MPC / MPCX",
            "IP",
        ]
        board.set("CIRASAME")
        assert target.get() == "cirasame"
        assert network_tabs.preset.get() == "in_125_out_500_125"
        board.set("STAG")
        assert "official reference" in board_status.get()
        board.set("AMANEQ")
        assert target.get() == "amaneq-v4"
        catalog_rows = [
            {
                "target": "amaneq-v4",
                "firmware": "lrtdc",
                "format": "mcs",
                "path": "mcs/amaneq-4-strlrtdc-v2.A.mcs",
                "name": "newest.mcs",
            },
            {
                "target": "amaneq-v4",
                "firmware": "hrtdc",
                "format": "mcs",
                "path": "mcs/amaneq-4-strhrtdc-v2.A.mcs",
                "name": "other.mcs",
            },
            {
                "target": "amaneq-v1",
                "firmware": "lrtdc",
                "format": "mcs",
                "path": "mcs/amaneq-1-strlrtdc-v2.A.mcs",
                "name": "wrong-target.mcs",
            },
        ]
        for key, label in firmware_labels.items():
            firmware_display.set(label)
            firmware_picked()
            assert firmware.get() == key
            assert firmware_display.get() == label
        firmware.set("lrtdc")
        profile_changed()
        show_catalog()
        assert images.get_children() == ("0",)
        assert images.selection() == ("0",)
        target.set("hrtdc-mezzanine")
        profile_changed()
        assert firmware.get() == "hrtdc"
        assert not firmware_box.winfo_manager()
        target.set("amaneq-v4")
        firmware.set("skeleton")
        profile_changed()
        assert tuple(format_box["values"]) == tuple(format_labels.values())
        image_format.set(format_labels["bit"])
        firmware.set("lrtdc")
        profile_changed()
        assert image_format.get() == ".bit file"
        network_tabs.file.set("/" + "long-directory/" * 100 + "example.mpcx")
        notebook.select(2)
        root.update()
        network_tabs.file_entry.focus_force()
        root.update()
        network_tabs.file_entry.event_generate("<End>")
        root.update()
        assert network_tabs.file_entry.index("insert") == len(network_tabs.file.get())
        assert network_tabs.file_entry.xview()[0] > 0
        network_tabs.file_entry.event_generate("<Home>")
        root.update()
        assert network_tabs.file_entry.index("insert") == 0
        assert network_tabs.file_entry.xview()[0] == 0
        network_tabs.file_entry.event_generate("<Right>")
        root.update()
        assert network_tabs.file_entry.index("insert") == 1
        network_tabs.file.set("")
        for endpoint in ("192.168.10.16", "192.168.10.10", "192.168.2.5"):
            network_tabs.clock_target.set(endpoint)
            assert network_tabs.clock_target.value() == endpoint
            if endpoint in ("192.168.10.10", "192.168.10.16"):
                assert "default)" in network_tabs.clock_target.choice.get()
        network_tabs.clock_target.set("192.168.10.10")
        assert not temporary_enabled.get()
        temporary_enabled.set(True)
        toggle_temporary()
        temporary_enabled.set(False)
        toggle_temporary()
        source_mode.set("Local")
        change_source()
        source_mode.set("GitHub")
        change_source()
        for tab in notebook.tabs():
            notebook.select(tab)
            root.update_idletasks()
        notebook.select(0)
        root.update_idletasks()
        original_sash = split.sashpos(0)
        split.sashpos(0, max(80, original_sash - 80))
        assert split.sashpos(0) < original_sash
        split.sashpos(0, original_sash)
        zoom.set("125%")
        resize_ui()
        zoom.set("100%")
        resize_ui()
        for index in range(100):
            log.insert("end", f"Synthetic message {index}\n")
        first_messages()
        assert not follow_messages.get()
        position = log.yview()[0]
        events.put(("log", "Synthetic message while viewing history"))
        poll()
        root.update_idletasks()
        assert log.yview()[0] == position
        latest_messages()
        assert follow_messages.get()
        root.after(300, root.destroy)
    else:
        root.after(50, lambda: scan(quiet=True))
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
