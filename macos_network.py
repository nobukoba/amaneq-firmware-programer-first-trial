"""Temporary macOS IPv4 aliases with a narrowly scoped administrator helper."""

import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import time
import uuid


class NetworkError(RuntimeError):
    pass


def run(arguments, timeout=20):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise NetworkError(
            result.stderr.strip()
            or result.stdout.strip()
            or f"Command failed: {arguments[0]}"
        )
    return result.stdout


def ethernet_adapters():
    if sys.platform != "darwin":
        return []
    text = run(["/usr/sbin/networksetup", "-listallhardwareports"])
    adapters = []
    for block in text.split("\n\n"):
        port = re.search(r"^Hardware Port: (.+)$", block, re.M)
        device = re.search(r"^Device: (en\d+)$", block, re.M)
        if (
            port
            and device
            and not re.search(r"wi-fi|airport|bluetooth|bridge", port[1], re.I)
        ):
            adapters.append({"interface": device[1], "name": port[1]})
    return adapters


def parse_addresses(text):
    current = None
    result = []
    for line in text.splitlines():
        header = re.match(r"^([a-zA-Z0-9]+):", line)
        if header:
            current = header[1]
        address = re.search(
            r"\binet (\d+\.\d+\.\d+\.\d+)\s+netmask (0x[0-9a-fA-F]+|[0-9.]+)", line
        )
        if address and current:
            mask = address[2]
            if mask.startswith("0x"):
                mask = str(ipaddress.IPv4Address(int(mask, 16)))
            result.append({"interface": current, "address": address[1], "mask": mask})
    return result


def all_addresses():
    return parse_addresses(run(["/sbin/ifconfig", "-a"]))


def validate_configuration(interface, address, mask, existing):
    if not re.fullmatch(r"en\d+", interface):
        raise NetworkError("Select an Ethernet interface from the adapter list.")
    try:
        value = ipaddress.IPv4Interface(f"{address}/{mask}")
    except ValueError as error:
        raise NetworkError(
            "Enter a valid IPv4 host address and contiguous subnet mask."
        ) from error
    if (
        value.ip.is_multicast
        or value.ip.is_loopback
        or value.ip.is_unspecified
        or value.ip.is_reserved
    ):
        raise NetworkError(
            "The temporary address must be a usable unicast IPv4 address."
        )
    if (
        value.network.prefixlen < 1
        or value.network.prefixlen > 30
        or value.ip in (value.network.network_address, value.network.broadcast_address)
    ):
        raise NetworkError(
            "Use a host address with a subnet prefix between /1 and /30."
        )
    effective_mask = str(value.netmask)
    for item in existing:
        other = ipaddress.IPv4Interface(f"{item['address']}/{item['mask']}")
        if other.ip == value.ip:
            raise NetworkError(
                "That IPv4 address is already assigned; the app will not adopt or remove it."
            )
        if item["interface"] != interface and other.network.overlaps(value.network):
            raise NetworkError(
                f"The subnet overlaps {item['interface']}. Select the correct adapter or a separate subnet."
            )
        if item["interface"] == interface and value.network.subnet_of(other.network):
            effective_mask = "255.255.255.255"
    return str(value.ip), str(value.netmask), effective_mask


def interface_mac(interface):
    text = run(["/sbin/ifconfig", interface])
    match = re.search(r"\bether ([0-9a-f:]{17})", text, re.I)
    if not match:
        raise NetworkError(
            "Cannot identify the selected Ethernet adapter's MAC address."
        )
    return match[1].lower()


def process_identity(pid):
    result = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def create_lease(root, interface, address, mask):
    address, mask, effective = validate_configuration(
        interface, address, mask, all_addresses()
    )
    if interface not in [item["interface"] for item in ethernet_adapters()]:
        raise NetworkError("The selected Ethernet adapter is no longer available.")
    token = uuid.uuid4().hex
    path = root / "network-leases" / (token + ".json")
    record = {
        "token": token,
        "interface": interface,
        "address": address,
        "mask": mask,
        "effective_mask": effective,
        "mac": interface_mac(interface),
        "parent_pid": os.getpid(),
        "parent_uid": os.getuid(),
        "parent_identity": process_identity(os.getpid()),
        "release": False,
    }
    save(path, record)
    return path, record


def read_lease(path):
    import pwd

    path = Path(path)
    if not re.fullmatch(r"[0-9a-f]{32}\.json", path.name) or path.is_symlink():
        raise NetworkError("Invalid network lease path.")
    details = path.stat()
    if not stat.S_ISREG(details.st_mode) or details.st_mode & 0o022:
        raise NetworkError(
            "Network lease must be a regular file not writable by other users."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    uid = int(data["parent_uid"])
    if (
        not isinstance(data["parent_pid"], int)
        or data["parent_pid"] <= 1
        or not data.get("parent_identity")
    ):
        raise NetworkError("Invalid requesting process identity.")
    home = Path(pwd.getpwuid(uid).pw_dir)
    expected = home / "Library/Application Support/AMANEQ/network-leases"
    if (
        details.st_uid != uid
        or path.resolve().parent != expected.resolve()
        or data["token"] != path.stem
    ):
        raise NetworkError("Network lease ownership/location mismatch.")
    validate_configuration(data["interface"], data["address"], data["mask"], [])
    if data["effective_mask"] not in (data["mask"], "255.255.255.255"):
        raise NetworkError("Invalid effective alias mask.")
    if not re.fullmatch(r"[0-9a-f:]{17}", data["mac"]):
        raise NetworkError("Invalid adapter identity.")
    return data


def alias_present(data):
    return any(
        item["interface"] == data["interface"] and item["address"] == data["address"]
        for item in all_addresses()
    )


def remove_alias(data):
    if not alias_present(data):
        return
    if interface_mac(data["interface"]) != data["mac"]:
        raise NetworkError(
            "Adapter identity changed; automatic address removal refused."
        )
    current = [
        item
        for item in all_addresses()
        if item["interface"] == data["interface"] and item["address"] == data["address"]
    ]
    if len(current) != 1 or current[0]["mask"] != data["effective_mask"]:
        raise NetworkError(
            "The alias was changed outside this app; automatic removal refused."
        )
    run(["/sbin/ifconfig", data["interface"], "inet", data["address"], "-alias"])
    if alias_present(data):
        raise NetworkError(
            "The temporary IPv4 alias remains present. Inspect the adapter before retrying."
        )


def privileged(action, path, prefix):
    if sys.platform != "darwin" or os.geteuid() != 0:
        raise NetworkError(
            "Temporary network changes require macOS administrator approval."
        )
    data = read_lease(path)
    if action == "remove":
        remove_alias(data)
        return {"success": True, "action": action}
    if action == "guard":
        # A separate privileged process removes only this alias after exit/crash.
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
            remove_alias(data)
        return {"success": True, "action": action}
    if action != "apply":
        raise NetworkError("Unknown network operation.")
    if data.get("release"):
        raise NetworkError("This network lease has already been released.")
    if (
        not data["parent_identity"]
        or process_identity(data["parent_pid"]) != data["parent_identity"]
    ):
        raise NetworkError("The requesting application is no longer running.")
    address, mask, effective = validate_configuration(
        data["interface"], data["address"], data["mask"], all_addresses()
    )
    if (
        effective != data["effective_mask"]
        or interface_mac(data["interface"]) != data["mac"]
    ):
        raise NetworkError(
            "The network adapter/address state changed before confirmation."
        )
    run(
        [
            "/sbin/ifconfig",
            data["interface"],
            "inet",
            address,
            "netmask",
            effective,
            "alias",
        ]
    )
    try:
        if not alias_present(data):
            raise NetworkError("The temporary IPv4 alias was not observed.")
        child = subprocess.Popen(
            prefix + ["--network-worker", "guard", "--lease", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(0.3)
        if child.poll() is not None:
            raise NetworkError("The automatic network cleanup helper could not start.")
    except Exception:
        remove_alias(data)
        raise
    return {
        "success": True,
        "action": action,
        "guard_pid": child.pid,
        "address": address,
        "interface": data["interface"],
    }


def authorize(action, path, prefix):
    command = shlex.join(prefix + ["--network-worker", action, "--lease", str(path)])
    script = (
        "do shell script "
        + json.dumps(command, ensure_ascii=False)
        + " with administrator privileges"
    )
    return json.loads(run(["/usr/bin/osascript", "-e", script], timeout=180))


def release(path, data, prefix):
    signal = json.loads(path.read_text(encoding="utf-8"))
    signal["release"] = True
    save(path, signal)
    for _ in range(8):
        if not alias_present(data):
            path.unlink(missing_ok=True)
            return
        time.sleep(0.5)
    # Recover if the original cleanup process failed; do not alter DHCP settings.
    authorize("remove", path, prefix)
    if alias_present(data):
        raise NetworkError(
            "The temporary address is still present; keep the app open and inspect the adapter."
        )
    path.unlink(missing_ok=True)
