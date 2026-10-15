#!/usr/bin/env python3
"""Desktop front end with explicit, elevated Windows HS3 USB actions."""

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

ROOT = Path(__file__).resolve().parent


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
    spec.loader.exec_module(module)
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
    root.geometry("920x680")
    events = queue.Queue()
    busy = False
    selected_devices = []
    serial = tk.StringVar()
    loader = tk.StringVar(
        value=(
            str(ROOT / "runtime" / "ucrt64" / "bin" / "openFPGALoader.exe")
            if os.name == "nt"
            and (ROOT / "runtime" / "ucrt64" / "bin" / "openFPGALoader.exe").exists()
            else "openFPGALoader"
        )
    )
    firmware = tk.StringVar(value="lrtdc")
    target = tk.StringVar(value="amaneq-v4")
    filename = tk.StringVar()
    is_hs3 = tk.BooleanVar(value=False)
    notebook = ttk.Notebook(root)
    notebook.pack(fill="x", padx=12, pady=8)
    program_tab = ttk.Frame(notebook, padding=12)
    usb_tab = ttk.Frame(notebook, padding=12)
    notebook.add(program_tab, text="Firmware")
    notebook.add(usb_tab, text="Windows HS3 USB")
    log = tk.Text(root, wrap="word", height=17)
    log.pack(fill="both", expand=True, padx=12, pady=8)

    def launch(task):
        nonlocal busy
        if busy:
            messagebox.showinfo("Busy", "Wait for the current operation to finish.")
            return
        busy = True

        def execute():
            try:
                task()
            except Exception as error:
                events.put(("error", str(error)))
            finally:
                events.put(("done", ""))

        threading.Thread(target=execute, daemon=True).start()

    def process(command):
        events.put(("log", subprocess.list2cmdline(command)))
        with subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env={
                **os.environ,
                "PYTHONUNBUFFERED": "1",
                "AMANEQ_CYGPATH_DIR": str(ROOT / "runtime" / "msys" / "bin"),
            },
        ) as child:
            for line in child.stdout:
                events.put(("log", line.rstrip()))
            if child.wait():
                raise usb.DriverError(
                    f"Command failed with exit {child.returncode}. See the log."
                )

    def refresh():
        def task():
            found = usb.devices()
            events.put(("devices", found))

        launch(task)

    def change_driver(action):
        chosen = serial.get()
        try:
            device = usb.select(chosen, selected_devices)
            if not is_hs3.get():
                raise usb.DriverError(
                    "Confirm that this physical FT232H device is a Digilent HS3."
                )
        except Exception as error:
            messagebox.showerror("USB selection", str(error))
            return
        verb = (
            "Install WinUSB"
            if action == "winusb"
            else "Restore the saved FTDIBUS driver"
        )
        if not messagebox.askyesno(
            "Confirm USB driver change",
            f"{verb} for serial {chosen}?\nCurrent driver: {device['service']}\nClose Vivado and other cable applications first.\n\nDriver packages match a hardware ID; other FT232H devices can be affected when reconnected.\nThe original driver backup is preserved. Windows will request administrator approval.",
        ):
            return

        def task():
            token = uuid.uuid4().hex
            code = elevated(
                ["--usb-worker", action, "--serial", chosen, "--operation-token", token]
            )
            path = usb.state_root() / f"result-{token}.json"
            if not path.exists():
                raise usb.DriverError(
                    "No helper report was found. Use the same Windows account for administrator approval and inspect the device status before retrying."
                )
            result = json.loads(path.read_text(encoding="utf-8"))
            events.put(("log", json.dumps(result, indent=2)))
            if code or not result["success"]:
                raise usb.DriverError(result.get("error", "Driver helper failed."))
            events.put(("devices", usb.devices()))

        launch(task)

    ttk.Label(program_tab, text="openFPGALoader").grid(row=0, column=0, sticky="w")
    ttk.Entry(program_tab, textvariable=loader, width=65).grid(
        row=0, column=1, columnspan=2, sticky="ew"
    )
    ttk.Button(
        program_tab,
        text="Browse",
        command=lambda: loader.set(filedialog.askopenfilename() or loader.get()),
    ).grid(row=0, column=3)
    ttk.Label(program_tab, text="Serial (required for multiple cables)").grid(
        row=1, column=0, sticky="w"
    )
    ttk.Entry(program_tab, textvariable=serial).grid(row=1, column=1, sticky="ew")
    ttk.Combobox(
        program_tab,
        textvariable=firmware,
        state="readonly",
        values=("lrtdc", "hrtdc", "lrtdc-10g", "mikumari", "skeleton"),
    ).grid(row=2, column=0)
    ttk.Combobox(
        program_tab,
        textvariable=target,
        state="readonly",
        values=("amaneq-v1", "amaneq-v4", "hrtdc-mezzanine"),
    ).grid(row=2, column=1)
    ttk.Entry(program_tab, textvariable=filename, width=65).grid(
        row=3, column=0, columnspan=3, sticky="ew"
    )
    ttk.Button(
        program_tab,
        text="Local file",
        command=lambda: filename.set(filedialog.askopenfilename() or filename.get()),
    ).grid(row=3, column=3)

    def program(latest):
        args = [
            "program",
            "--loader",
            loader.get(),
            "--firmware",
            firmware.get(),
            "--target",
            target.get(),
            "--cable",
            "hs3",
            "--yes",
        ]
        if serial.get():
            args += ["--serial", serial.get()]
        if latest:
            args += ["--latest", "--format", "mcs"]
        elif filename.get():
            args += ["--file", filename.get()]
        else:
            messagebox.showerror("Firmware", "Choose a local file first.")
            return
        if not is_hs3.get():
            messagebox.showerror(
                "Cable",
                "Confirm that the selected physical cable is a Digilent HS3 on the USB tab.",
            )
            return
        if messagebox.askyesno(
            "Program firmware",
            f"Program {target.get()} with {firmware.get()}?\nMCS writes persistent flash; BIT replaces the running SRAM configuration.",
        ):
            launch(lambda: process(command_prefix() + ["--firmware-cli"] + args))

    ttk.Button(
        program_tab, text="Program latest MCS", command=lambda: program(True)
    ).grid(row=4, column=0, pady=8)
    ttk.Button(
        program_tab, text="Program local BIT/MCS", command=lambda: program(False)
    ).grid(row=4, column=1)
    ttk.Button(
        program_tab,
        text="Scan cables",
        command=lambda: launch(
            lambda: process(
                command_prefix() + ["--firmware-cli", "scan", "--loader", loader.get()]
            )
        ),
    ).grid(row=4, column=2)
    ttk.Label(
        usb_tab,
        text="Native Windows HS3 only. Connect exactly one FT232H during driver changes.\nUSB ID 0403:6014 alone does not prove the model. No driver changes occur during normal programming.",
    ).pack(anchor="w")
    cable = ttk.Combobox(usb_tab, textvariable=serial, state="readonly", width=60)
    cable.pack(anchor="w", pady=6)
    ttk.Checkbutton(
        usb_tab,
        variable=is_hs3,
        text="I confirm this physical cable is a Digilent JTAG-HS3",
    ).pack(anchor="w")
    controls = ttk.Frame(usb_tab)
    controls.pack(anchor="w", pady=6)
    for label, callback in [
        ("Refresh USB", refresh),
        ("Use openFPGALoader (WinUSB)", lambda: change_driver("winusb")),
        ("Restore Vivado driver", lambda: change_driver("restore")),
    ]:
        ttk.Button(
            controls,
            text=label,
            command=callback,
            state="normal" if os.name == "nt" else "disabled",
        ).pack(side="left", padx=3)

    def poll():
        nonlocal busy, selected_devices
        while not events.empty():
            kind, value = events.get_nowait()
            if kind == "done":
                busy = False
            elif kind == "devices":
                selected_devices = value
                cable["values"] = [item["serial"] for item in value]
                if serial.get() not in cable["values"]:
                    serial.set("")
                log.insert("end", json.dumps(value, indent=2) + "\n")
            else:
                log.insert("end", value + "\n")
                if kind == "error":
                    messagebox.showerror("Operation failed", value)
            log.see("end")
        root.after(100, poll)

    def close():
        if busy:
            messagebox.showinfo(
                "Operation running",
                "Wait for completion. Closing during programming or a driver change can leave an incomplete operation.",
            )
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    poll()
    if smoke_test:
        root.after(300, root.destroy)
    root.mainloop()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--firmware-cli":
        return firmware_cli(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--usb-worker", choices=("winusb", "restore"), help=argparse.SUPPRESS
    )
    parser.add_argument("--serial", help=argparse.SUPPRESS)
    parser.add_argument("--operation-token", help=argparse.SUPPRESS)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Build and close the desktop window without hardware operations",
    )
    args = parser.parse_args()
    if args.usb_worker:
        return worker(args.usb_worker, args.serial, args.operation_token)
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
