"""Explicit Windows HS3 driver switching; never called by normal programming."""

import contextlib
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


class DriverError(RuntimeError):
    pass


def state_root():
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AMANEQ" / "usb-drivers"


def run(command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise DriverError(
            f"Command failed ({result.returncode}): {result.stderr or result.stdout}"
        )
    return result.stdout


def devices():
    if os.name != "nt":
        raise DriverError("Driver switching is available only in native Windows.")
    query = r"""$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new();$result=@(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -match '^USB\\VID_0403&PID_6014\\'} | ForEach-Object {$d=$_;$p=@{};foreach($key in @('Service','DriverInfPath','BusReportedDeviceDesc','HardwareIds')){$p[$key]=(Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName ('DEVPKEY_Device_'+$key) -ErrorAction Stop).Data};[pscustomobject]@{instance=$d.InstanceId;serial=$d.InstanceId.Split('\')[-1];description=$p.BusReportedDeviceDesc;service=$p.Service;inf=$p.DriverInfPath;hardware_ids=@($p.HardwareIds)}});ConvertTo-Json -InputObject $result -Depth 4 -Compress"""
    return json.loads(
        run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query])
        or "[]"
    )


def select(serial, found):
    # A hardware-ID driver binding can affect every matching FT232H, not just one serial.
    if len(found) != 1:
        listing = ", ".join(item["serial"] for item in found) or "none"
        raise DriverError(
            f"Connect exactly one FT232H/HS3 for driver changes. Connected serials: {listing}"
        )
    if not serial or found[0]["serial"].casefold() != serial.casefold():
        raise DriverError("The explicitly selected HS3 serial is no longer present.")
    return found[0]


def directory_for(serial):
    return state_root() / hashlib.sha256(serial.casefold().encode()).hexdigest()[:24]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def file_hashes(directory):
    for item in directory.rglob("*"):
        if not item.resolve().is_relative_to(directory.resolve()):
            raise DriverError("Driver backup contains a path outside its directory.")
    return {
        p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def checked_backup(device):
    base = directory_for(device["serial"])
    manifest_path = base / "original.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_backup(device, base, manifest)
        return base, manifest
    if (device.get("service") or "").casefold() != "ftdibus":
        raise DriverError(
            "The original FTDIBUS driver must be active before the first backup. No saved original driver is available."
        )
    if not re.fullmatch(r"oem\d+\.inf", device["inf"], re.I):
        raise DriverError("Cannot export an unexpected original driver INF.")
    original = base / "original"
    original.mkdir(parents=True, exist_ok=True)
    # Do not merge remnants from an interrupted export into a new backup.
    if any(original.iterdir()):
        raise DriverError(
            f"Incomplete backup exists at {original}. Preserve it and inspect it before retrying."
        )
    run(["pnputil.exe", "/export-driver", device["inf"], str(original)])
    candidates = list(original.rglob("ftdibus.inf"))
    if len(candidates) != 1:
        raise DriverError(
            "Export did not produce exactly one ftdibus.inf. No driver changed."
        )
    manifest = {
        "schema": 1,
        "device": device,
        "inf": candidates[0].relative_to(original).as_posix(),
        "sha256": file_hashes(original),
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    write_json(manifest_path, manifest)
    return base, manifest


def validate_backup(device, base, manifest):
    if (
        manifest.get("schema") != 1
        or manifest["device"]["instance"].casefold() != device["instance"].casefold()
    ):
        raise DriverError(
            "Backup belongs to another device or has an unsupported schema."
        )
    original = (base / "original").resolve()
    inf = (original / manifest["inf"]).resolve()
    if not inf.is_relative_to(original) or inf.name.lower() != "ftdibus.inf":
        raise DriverError("Invalid original driver path.")
    if not manifest.get("sha256") or file_hashes(original) != manifest["sha256"]:
        raise DriverError(
            "Original driver backup is incomplete or has changed; restore refused."
        )
    return inf


class WdiDevice(c.Structure):
    pass


WdiDevice._fields_ = [
    ("next", c.POINTER(WdiDevice)),
    ("vid", c.c_uint16),
    ("pid", c.c_uint16),
    ("is_composite", c.c_int32),
    ("mi", c.c_ubyte),
    ("desc", c.c_char_p),
    ("driver", c.c_char_p),
    ("device_id", c.c_char_p),
    ("hardware_id", c.c_char_p),
    ("compatible_id", c.c_char_p),
    ("upper_filter", c.c_char_p),
    ("driver_version", c.c_uint64),
]


class WdiListOptions(c.Structure):
    _fields_ = [
        ("list_all", c.c_int32),
        ("list_hubs", c.c_int32),
        ("trim_whitespaces", c.c_int32),
    ]


class WdiPrepareOptions(c.Structure):
    _fields_ = [
        ("driver_type", c.c_int),
        ("vendor_name", c.c_char_p),
        ("device_guid", c.c_char_p),
        ("disable_cat", c.c_int32),
        ("disable_signing", c.c_int32),
        ("cert_subject", c.c_char_p),
        ("use_wcid_driver", c.c_int32),
        ("external_inf", c.c_int32),
    ]


class LibWdi:
    def __init__(self, path):
        if os.name != "nt" or c.sizeof(c.c_void_p) != 8:
            raise DriverError(
                "The bundled driver helper requires native Windows x64 and 64-bit Python."
            )
        self.dll = c.WinDLL(str(Path(path).resolve()))
        ptr = c.POINTER(WdiDevice)
        self.dll.wdi_strerror.argtypes = [c.c_int]
        self.dll.wdi_strerror.restype = c.c_char_p
        self.dll.wdi_create_list.argtypes = [c.POINTER(ptr), c.POINTER(WdiListOptions)]
        self.dll.wdi_destroy_list.argtypes = [ptr]
        self.dll.wdi_prepare_driver.argtypes = [
            ptr,
            c.c_char_p,
            c.c_char_p,
            c.POINTER(WdiPrepareOptions),
        ]
        self.dll.wdi_install_driver.argtypes = [ptr, c.c_char_p, c.c_char_p, c.c_void_p]

    def check(self, code):
        if code:
            raise DriverError(self.dll.wdi_strerror(code).decode("utf-8", "replace"))

    @contextlib.contextmanager
    def selected(self, instance):
        head = c.POINTER(WdiDevice)()
        self.check(
            self.dll.wdi_create_list(c.byref(head), c.byref(WdiListOptions(1, 0, 1)))
        )
        try:
            matches = []
            node = head
            while node:
                item = node.contents
                if (
                    item.device_id
                    and item.device_id.decode("utf-8").casefold() == instance.casefold()
                ):
                    matches.append(node)
                node = item.next
            if len(matches) != 1:
                raise DriverError(
                    "libwdi cannot uniquely locate the selected instance."
                )
            if matches[0].contents.vid != 0x0403 or matches[0].contents.pid != 0x6014:
                raise DriverError("Unexpected device identity from libwdi.")
            yield matches[0]
        finally:
            self.dll.wdi_destroy_list(head)

    def install(self, device, destination):
        with self.selected(device["instance"]) as node:
            options = WdiPrepareOptions()  # WinUSB=0; keep catalog/signing enabled.
            path = str(destination).encode("utf-8")
            self.check(
                self.dll.wdi_prepare_driver(
                    node, path, b"amaneq-hs3-winusb.inf", c.byref(options)
                )
            )
            self.check(
                self.dll.wdi_install_driver(node, path, b"amaneq-hs3-winusb.inf", None)
            )


def restore_driver(inf):
    library = c.WinDLL("newdev.dll", use_last_error=True)
    update = library.UpdateDriverForPlugAndPlayDevicesW
    update.argtypes = [
        c.c_void_p,
        c.c_wchar_p,
        c.c_wchar_p,
        c.c_uint32,
        c.POINTER(c.c_int32),
    ]
    update.restype = c.c_int32
    reboot = c.c_int32()
    if not update(None, "USB\\VID_0403&PID_6014", str(inf), 1, c.byref(reboot)):
        raise c.WinError(c.get_last_error())
    return bool(reboot.value)


def wait_service(serial, expected):
    for _ in range(20):
        found = devices()
        if not found:
            time.sleep(1)
            continue
        current = select(serial, found)
        if (current.get("service") or "").casefold() == expected.casefold():
            return current
        time.sleep(1)
    raise DriverError(
        f"Driver command finished, but {expected} was not observed. Do not repeat blindly; inspect the saved state and reconnect if requested."
    )


@contextlib.contextmanager
def operation_lock():
    import msvcrt

    root = state_root()
    root.mkdir(parents=True, exist_ok=True)
    with (root / "operation.lock").open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise DriverError("Another USB driver operation is running.") from error
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def perform(action, serial, dll):
    if os.name != "nt" or not c.windll.shell32.IsUserAnAdmin():
        raise DriverError("Driver changes require Windows administrator approval.")
    with operation_lock():
        device = select(serial, devices())
        if action == "winusb":
            if (device.get("service") or "").casefold() == "winusb":
                raise DriverError("WinUSB is already active; no change needed.")
            helper = LibWdi(
                dll
            )  # Check availability before exporting/changing anything.
            base, manifest = checked_backup(device)
            current = select(serial, devices())
            if current != device:
                raise DriverError(
                    "Device state changed after backup; no driver changed."
                )
            helper.install(device, base / "winusb")
            result = wait_service(serial, "WinUSB")
            reboot = False
        elif action == "restore":
            base = directory_for(serial)
            manifest = json.loads((base / "original.json").read_text(encoding="utf-8"))
            inf = validate_backup(device, base, manifest)
            current = select(serial, devices())
            if current != device:
                raise DriverError(
                    "Device state changed before restore; no driver changed."
                )
            reboot = restore_driver(inf)
            result = wait_service(serial, "FTDIBUS") if not reboot else device
        else:
            raise DriverError("Unknown driver operation.")
        return {
            "action": action,
            "device": result,
            "backup": str(base),
            "reboot_required": reboot,
        }
