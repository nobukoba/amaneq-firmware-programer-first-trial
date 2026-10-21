"""Temporary host addresses on Windows/Linux; retain the macOS implementation."""

import ctypes
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import time
import uuid

import macos_network as mac

NetworkError = mac.NetworkError
IS_WINDOWS = os.name == "nt"


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / ("." + uuid.uuid4().hex + ".tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def powershell(script, timeout=40):
    executable = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    result = subprocess.run(
        [
            str(executable),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
            + script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise NetworkError(
            result.stderr.strip() or result.stdout.strip() or "PowerShell failed."
        )
    return result.stdout


def windows_adapters():
    rows = json.loads(
        powershell(
            'ConvertTo-Json -Compress -InputObject @(Get-NetAdapter -Physical | Where-Object {$_.MediaType -eq "802.3"} | ForEach-Object { @{interface=[string]$_.ifIndex; name=$_.Name; mac=$_.MacAddress.ToLower().Replace("-",":")} })'
        )
    )
    return rows


def ip_command():
    # Fixed system locations avoid running a user-controlled executable as root.
    for candidate in ("/usr/sbin/ip", "/usr/bin/ip", "/sbin/ip", "/bin/ip"):
        if Path(candidate).is_file():
            return candidate
    raise NetworkError("Install iproute2 to use temporary host addresses.")


def linux_links():
    return json.loads(mac.run([ip_command(), "-j", "link", "show"]))


def ethernet_adapters():
    if sys.platform == "darwin":
        return mac.ethernet_adapters()
    if IS_WINDOWS:
        return windows_adapters()
    result = []
    for row in linux_links():
        name = row["ifname"]
        base = Path("/sys/class/net") / name
        if (
            row.get("link_type") == "ether"
            and (base / "device").exists()
            and not (base / "wireless").exists()
        ):
            result.append(
                {"interface": name, "name": name, "mac": row["address"].lower()}
            )
    return result


def all_addresses():
    if sys.platform == "darwin":
        return mac.all_addresses()
    if IS_WINDOWS:
        return json.loads(
            powershell(
                "ConvertTo-Json -Compress -InputObject @(Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { @{interface=[string]$_.InterfaceIndex; address=$_.IPAddress; prefix=[int]$_.PrefixLength; state=[string]$_.AddressState} })"
            )
        )
    result = []
    for row in json.loads(mac.run([ip_command(), "-j", "-4", "address", "show"])):
        for address in row.get("addr_info", []):
            result.append(
                {
                    "interface": row["ifname"],
                    "address": address["local"],
                    "prefix": address["prefixlen"],
                }
            )
    return result


def normalized_addresses():
    return [
        {
            **row,
            "mask": row.get("mask")
            or str(ipaddress.IPv4Network("0.0.0.0/" + str(row["prefix"])).netmask),
        }
        for row in all_addresses()
    ]


def validate_configuration(interface, address, mask, existing):
    if sys.platform == "darwin":
        return mac.validate_configuration(interface, address, mask, existing)
    pattern = r"[1-9][0-9]{0,9}" if IS_WINDOWS else r"[a-zA-Z0-9_.:-]{1,15}"
    if not re.fullmatch(pattern, interface):
        raise NetworkError("Select an Ethernet interface from the adapter list.")
    # Reuse the address/overlap validation without assuming a macOS interface name.
    mapped = [
        {
            **row,
            "interface": "en0" if row["interface"] == interface else row["interface"],
        }
        for row in existing
    ]
    return mac.validate_configuration("en0", address, mask, mapped)


def adapter_identity(interface):
    matches = [row for row in ethernet_adapters() if row["interface"] == interface]
    if len(matches) != 1 or not re.fullmatch(
        r"[0-9a-f]{2}(:[0-9a-f]{2}){5}", matches[0]["mac"]
    ):
        raise NetworkError("The selected physical Ethernet adapter is unavailable.")
    return matches[0]["mac"]


def process_identity(pid):
    if not IS_WINDOWS:
        try:
            return (
                Path("/proc/" + str(pid) + "/stat")
                .read_text()
                .rsplit(")", 1)[1]
                .split()[19]
            )
        except (OSError, IndexError):
            return ""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [
        ctypes.POINTER(ctypes.c_uint64)
    ] * 4
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ""
    values = [ctypes.c_uint64() for _ in range(4)]
    try:
        if not kernel.GetProcessTimes(
            handle, *(ctypes.byref(value) for value in values)
        ):
            return ""
        return str(values[0].value)
    finally:
        kernel.CloseHandle(handle)


def create_lease(root, interface, address, mask):
    if sys.platform == "darwin":
        return mac.create_lease(root, interface, address, mask)
    address, mask, effective = validate_configuration(
        interface, address, mask, normalized_addresses()
    )
    token = uuid.uuid4().hex
    path = root / "network-leases" / (token + ".json")
    data = dict(
        token=token,
        interface=interface,
        address=address,
        mask=mask,
        effective_mask=effective,
        mac=adapter_identity(interface),
        parent_pid=os.getpid(),
        parent_identity=process_identity(os.getpid()),
        release=False,
        applied=False,
    )
    if not IS_WINDOWS:
        data["parent_uid"] = os.getuid()
    save(path, data)
    return path, data


def read_lease(path):
    path = Path(path)
    if not re.fullmatch(r"[0-9a-f]{32}\.json", path.name) or path.is_symlink():
        raise NetworkError("Invalid network lease path.")
    details = path.stat()
    if not stat.S_ISREG(details.st_mode):
        raise NetworkError("Network lease must be a regular file.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if IS_WINDOWS:
        expected = Path(os.environ["LOCALAPPDATA"]) / "AMANEQ/network-leases"
    else:
        import pwd

        uid = data["parent_uid"]
        expected = Path(pwd.getpwuid(uid).pw_dir) / ".local/share/AMANEQ/network-leases"
        if details.st_uid != uid or details.st_mode & 0o022:
            raise NetworkError("Network lease ownership/permissions mismatch.")
        # pkexec preserves the original caller in PKEXEC_UID.
        if os.environ.get("PKEXEC_UID") and int(os.environ["PKEXEC_UID"]) != uid:
            raise NetworkError("Network lease caller mismatch.")
    if path.resolve().parent != expected.resolve() or data["token"] != path.stem:
        raise NetworkError(
            "Network lease ownership/location mismatch. Use the standard application data directory."
        )
    validate_configuration(data["interface"], data["address"], data["mask"], [])
    if data["effective_mask"] not in (
        data["mask"],
        "255.255.255.255",
    ) or not re.fullmatch(r"[0-9a-f]{2}(:[0-9a-f]{2}){5}", data["mac"]):
        raise NetworkError("Invalid network adapter/address identity.")
    if (
        not isinstance(data["parent_pid"], int)
        or data["parent_pid"] <= 1
        or not data["parent_identity"]
    ):
        raise NetworkError("Invalid requesting process identity.")
    return data


def alias_present(data):
    return any(
        row["interface"] == data["interface"] and row["address"] == data["address"]
        for row in all_addresses()
    )


def windows_address(action, data):
    # MIB_UNICASTIPADDRESS_ROW uses an 8-byte aligned SOCKADDR_INET/LUID layout.
    # Explicit offsets avoid ctypes host-dependent C long sizes in offline tests.
    row = (ctypes.c_uint64 * 10)()
    library = ctypes.WinDLL("iphlpapi", use_last_error=True)
    initialize = library.InitializeUnicastIpAddressEntry
    initialize.argtypes = [ctypes.c_void_p]
    initialize.restype = None
    initialize(ctypes.byref(row))
    pointer = ctypes.addressof(row)
    ctypes.memmove(
        pointer,
        struct.pack("<H", 2) + b"\0\0" + ipaddress.IPv4Address(data["address"]).packed,
        8,
    )
    ctypes.c_uint32.from_address(pointer + 40).value = int(data["interface"])
    ctypes.c_ubyte.from_address(pointer + 60).value = ipaddress.IPv4Network(
        "0.0.0.0/" + data["effective_mask"]
    ).prefixlen
    function = getattr(
        library,
        (
            "CreateUnicastIpAddressEntry"
            if action == "add"
            else "DeleteUnicastIpAddressEntry"
        ),
    )
    function.argtypes = [ctypes.c_void_p]
    function.restype = ctypes.c_uint32
    code = function(ctypes.byref(row))
    if code:
        raise NetworkError(f"{function.__name__} failed (Windows error {code}).")
    if action == "add":
        try:
            wait_for_windows_address(library, row, pointer)
        except Exception:
            windows_address("delete", data)
            raise


def wait_for_windows_address(library, row, pointer):
    getter = library.GetUnicastIpAddressEntry
    getter.argtypes = [ctypes.c_void_p]
    getter.restype = ctypes.c_uint32
    for _ in range(20):
        code = getter(ctypes.byref(row))
        state = ctypes.c_uint32.from_address(pointer + 64).value
        if not code and state == 4:  # IpDadStatePreferred
            return
        if code or state != 1:  # IpDadStateTentative
            raise NetworkError("Temporary IPv4 duplicate-address detection failed.")
        time.sleep(0.5)
    raise NetworkError("Temporary IPv4 did not become usable; check the Ethernet link.")


def change_address(action, data):
    if IS_WINDOWS:
        return windows_address(action, data)
    prefix = ipaddress.IPv4Network("0.0.0.0/" + data["effective_mask"]).prefixlen
    command = [
        ip_command(),
        "address",
        action,
        f"{data['address']}/{prefix}",
        "dev",
        data["interface"],
    ]
    mac.run(command)


def remove_alias(data):
    if not alias_present(data):
        return
    if adapter_identity(data["interface"]) != data["mac"]:
        raise NetworkError("Adapter identity changed; automatic removal refused.")
    rows = [
        row
        for row in normalized_addresses()
        if row["interface"] == data["interface"] and row["address"] == data["address"]
    ]
    if len(rows) != 1 or rows[0]["mask"] != data["effective_mask"]:
        raise NetworkError(
            "The address was changed outside this app; automatic removal refused."
        )
    change_address("delete" if IS_WINDOWS else "del", data)
    if alias_present(data):
        raise NetworkError(
            "The temporary IPv4 address remains present. Inspect the adapter."
        )


def privileged(action, path, prefix):
    if sys.platform == "darwin":
        return mac.privileged(action, path, prefix)
    admin = ctypes.windll.shell32.IsUserAnAdmin() if IS_WINDOWS else os.geteuid() == 0
    if not admin:
        raise NetworkError("Temporary network changes require administrator approval.")
    if action == "guard":
        # Snapshot arrives through the privileged parent's private pipe. Never reread
        # mutable lease fields to decide which address to remove.
        data = json.loads(sys.stdin.readline())
        try:
            while process_identity(data["parent_pid"]) == data["parent_identity"]:
                try:
                    signal = json.loads(Path(path).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    break
                if signal.get("token") != data["token"] or signal.get("release"):
                    break
                time.sleep(1)
        finally:
            try:
                remove_alias(data)
                save(
                    Path(path).with_suffix(".result"),
                    {"success": True, "action": "guard"},
                )
            except Exception as error:
                save(
                    Path(path).with_suffix(".result"),
                    {"success": False, "error": str(error)},
                )
        return {"success": True}
    data = read_lease(path)
    if action == "remove":
        remove_alias(data)
        return {"success": True}
    if action != "apply" or data.get("release"):
        raise NetworkError("Unknown operation or released network lease.")
    if process_identity(data["parent_pid"]) != data["parent_identity"]:
        raise NetworkError("The requesting application is no longer running.")
    address, mask, effective = validate_configuration(
        data["interface"], data["address"], data["mask"], normalized_addresses()
    )
    if (
        effective != data["effective_mask"]
        or adapter_identity(data["interface"]) != data["mac"]
    ):
        raise NetworkError("Network adapter/address state changed before confirmation.")
    # Roll back only after this invocation successfully creates an address.
    # Windows DAD failures are rolled back within windows_address.
    created = False
    try:
        if IS_WINDOWS:
            windows_address("add", data)
        else:
            change_address("add", data)
        created = True
        if not alias_present(data):
            raise NetworkError("The temporary address was not observed.")
        options = (
            {"creationflags": subprocess.CREATE_NO_WINDOW}
            if IS_WINDOWS
            else {"start_new_session": True}
        )
        child = subprocess.Popen(
            prefix + ["--network-worker", "guard", "--lease", str(path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            **options,
        )
        child.stdin.write(json.dumps(data) + "\n")
        child.stdin.close()
        time.sleep(0.3)
        if child.poll() is not None:
            raise NetworkError("The automatic cleanup helper could not start.")
    except Exception:
        if created:
            remove_alias(data)
        raise
    return {"success": True, "guard_pid": child.pid}


def authorize(action, path, prefix):
    if sys.platform == "darwin":
        return mac.authorize(action, path, prefix)
    report = Path(path).with_suffix(".result")
    report.unlink(missing_ok=True)
    command = prefix + ["--network-worker", action, "--lease", str(path)]
    if IS_WINDOWS:
        # Start-Process passes one Windows-quoted argument string, avoiding shell interpolation.
        quote = lambda value: "'" + value.replace("'", "''") + "'"
        script = (
            "$p=Start-Process -FilePath "
            + quote(command[0])
            + " -ArgumentList "
            + quote(subprocess.list2cmdline(command[1:]))
            + ' -Verb RunAs -WindowStyle Hidden -Wait -PassThru; if ($p.ExitCode) {throw "Network helper failed"}'
        )
        powershell(script, timeout=180)
    else:
        pkexec = shutil.which("pkexec")
        if not pkexec:
            raise NetworkError(
                "Install policykit/pkexec with a desktop authentication agent to authorize temporary IP changes."
            )
        mac.run([pkexec] + command, timeout=180)
    result = json.loads(report.read_text(encoding="utf-8"))
    if not result.get("success"):
        raise NetworkError(result.get("error", "Network helper failed."))
    return result


def release(path, data, prefix):
    if sys.platform == "darwin":
        return mac.release(path, data, prefix)
    signal = json.loads(path.read_text(encoding="utf-8"))
    signal["release"] = True
    save(path, signal)
    for _ in range(16):
        if not alias_present(data):
            path.unlink(missing_ok=True)
            return
        time.sleep(0.5)
    if not data.get("applied"):
        raise NetworkError(
            "No confirmed address ownership. Inspect the adapter; automatic removal refused."
        )
    authorize("remove", path, prefix)
    if alias_present(data):
        raise NetworkError(
            "The temporary address remains present. Keep the app open and inspect the adapter."
        )
    path.unlink(missing_ok=True)
