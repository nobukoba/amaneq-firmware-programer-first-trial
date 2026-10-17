"""RBCP clock configuration and validated command construction for desktop tabs."""

import ipaddress
from pathlib import Path
import shutil
import subprocess
import sys
import socket
import struct

# hul-common-lib CDCE62002RegMap.hh: input MHz and output MHz are in the names.
PRESETS = {
    "in_100_out_500_100": (0x52880150, 0x8F81C061),
    "in_125_out_500_125": (0x52080150, 0x8F81C081),
    "in_125_out_625_125": (0x52880150, 0x8F81A061),
    "in_75_out_375_75": (0x52880150, 0x8F818061),
    "in_50_out_250_50": (0x55100150, 0x8F81C021),
    "in_100_out_250_50": (0x55100150, 0x8F81C061),
}


DEFAULT_CLOCK_PRESET = "in_125_out_500_125"
CLOCK_CHOICES = tuple(PRESETS)


def resolve_clock_preset(value):
    """Validate the original hul-common-lib command argument."""
    value = value.strip()
    if value in PRESETS:
        return value
    raise ValueError(
        "Unsupported clock preset. Choose or enter a listed in_*_out_*_* value."
    )


def ipv4(value):
    address = ipaddress.IPv4Address(value.strip())
    if (
        address.is_unspecified
        or address.is_multicast
        or address.is_loopback
        or address.is_reserved
    ):
        raise ValueError("Enter a unicast device IPv4 address.")
    return str(address)


def endpoint(mode, custom):
    return (
        ipv4(custom)
        if mode == "Custom"
        else {"MPCX": "192.168.10.10", "MPC": "192.168.10.16"}[mode]
    )


def reverse32(value):
    return int(f"{value:032b}"[::-1], 2)


class Rbcp:
    def __init__(self, host, port=4660, timeout=3):
        self.host = ipv4(host)
        self.port = port
        self.timeout = timeout
        self.ident = 0

    def exchange(self, command, address, payload=b"", length=1):
        self.ident = (self.ident + 1) & 255
        header = struct.pack("!BBBBI", 255, command, self.ident, length, address)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(self.timeout)
                client.connect((self.host, self.port))
                client.send(header + payload)
                reply = client.recv(512)
        except OSError as error:
            raise RuntimeError(
                f"RBCP {self.host}:{self.port} failed: {error}. Check Ethernet, temporary IP and the target address. No automatic write retry was made."
            ) from error
        expected = struct.pack("!BBBBI", 255, command | 8, self.ident, length, address)
        if len(reply) != 8 + length or reply[:8] != expected:
            raise RuntimeError(
                "Invalid RBCP ACK, bus error or short response. Operation stopped."
            )
        if command == 0x80 and reply[8:] != payload:
            raise RuntimeError(
                "RBCP write acknowledgement data differs from the request."
            )
        return reply[8:]

    def read(self, address):
        return self.exchange(0xC0, address)[0]

    def write(self, address, value):
        self.exchange(0x80, address, bytes([value]), 1)


def write_word(client, address, value):
    # HUL multi-byte registers use byte lanes spaced by 0x10000, little-endian.
    for lane in range(4):
        client.write(address + (lane << 16), (value >> (8 * lane)) & 255)


def read_clock(client, register):
    write_word(client, 0xB0000000, reverse32((register << 4) | 0xE))
    client.read(0xB2000000)
    value = sum(
        client.read(0xB0100000 + (lane << 16)) << (8 * lane) for lane in range(4)
    )
    return reverse32(value)


def configure_clock(host, preset, persist=False, client_factory=Rbcp):
    values = PRESETS[preset]
    client = client_factory(ipv4(host))
    before = [read_clock(client, index) for index in range(2)]
    for value in values:
        write_word(client, 0xB0000000, reverse32(value))
        client.write(0xB1000000, 0)
    after = [read_clock(client, index) for index in range(2)]
    if after != list(values):
        raise RuntimeError(
            f"CDCE62002 readback mismatch: expected {[hex(v) for v in values]}, got {[hex(v) for v in after]}. EEPROM copy was not sent."
        )
    if persist:
        write_word(client, 0xB0000000, reverse32(0x1F))
        client.write(0xB1000000, 0)
    return (
        f"CDCE62002 registers verified. Before: {[hex(v) for v in before]}; after: {[hex(v) for v in after]}. "
        + (
            "EEPROM copy command acknowledged; power-cycle persistence is unverified."
            if persist
            else "Runtime registers only; EEPROM unchanged."
        )
    )


def license_kind(path):
    path = Path(path)
    if path.stat().st_size != 22:
        raise ValueError("MPC/MPCX files must contain exactly 22 bytes.")
    data = path.read_bytes()
    if len(data) != 22:
        raise ValueError("MPC/MPCX files must contain exactly 22 bytes.")

    def valid_tag(offset, delta):
        decoded = [
            (value - delta) & 255 if value else 0 for value in data[offset : offset + 7]
        ]
        return all(
            value in (0, 32, 45) or 48 <= value <= 57 or 65 <= (value & 0xDF) <= 90
            for value in decoded
        )

    # Upstream type 2 is normal SiTCP/MPC; type 1 is SiTCP-XG/MPCX.
    if valid_tag(6, 0x34):
        return "MPC"
    if valid_tag(0, 0x2C):
        return "MPCX"
    raise ValueError("File contents do not match the referenced MPC/MPCX format.")


def ping_command(host, platform=None):
    host = ipv4(host)
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        return ["ping", "-n", "2", "-w", "1000", host]
    return [
        "/sbin/ping" if platform == "darwin" else "ping",
        "-n",
        "-c",
        "2",
        "-W",
        "1000" if platform == "darwin" else "1",
        host,
    ]


def ping_target(host):
    command = ping_command(host)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return False, f"Ping to {host} timed out after 8 seconds."
    except OSError as error:
        raise RuntimeError(f"Could not run ping: {error}") from error
    return result.returncode == 0, result.stdout.strip() + "\n" + result.stderr.strip()


def utility_path(root, name):
    candidate = Path(root) / "runtime/network/bin" / name
    if candidate.is_file():
        return str(candidate)
    installed = shutil.which(name)
    if installed:
        return installed
    raise RuntimeError(
        f"Missing {name}. Use the bundled macOS app or run build-network-tools.py on Linux/WSL/macOS."
    )


def utility_command(
    root, host, action, filename="", new_ip="", current=False, initialize=False
):
    host = ipv4(host)
    if action == "Read":
        return [utility_path(root, "mpc-mpcx-ip-reader"), host]
    if action == "Read IP":
        return [utility_path(root, "sitcp-sitcpxg-ip-reader"), host]
    if action == "Write IP only":
        return [
            utility_path(root, "sitcp-sitcpxg-ip-writer"),
            host,
            ipv4(new_ip),
            "--current" if current else "--eeprom",
        ]
    command = [utility_path(root, "mpc-mpcx-ip-writer"), host]
    if filename:
        path = Path(filename).expanduser().resolve()
        if not path.is_file() or path.stat().st_size != 22:
            raise ValueError(
                "Choose a valid 22-byte MPC/MPCX file. The utility checks its contents and device generation."
            )
        command.append(str(path))
    elif action != "Check":
        raise ValueError("Choose an MPC/MPCX file first.")
    if action == "Check":
        return command + ["--check"]
    if initialize:
        command.append("--initialize-eeprom")
    if new_ip.strip():
        command += ["--set-current-ip" if current else "--set-eeprom-ip", ipv4(new_ip)]
    return command


def get_version(host, client_factory=Rbcp):
    """Read the HUL common BCT version register without writing hardware."""
    host = ipv4(host)
    client = client_factory(host)
    # hul-common-lib RegisterMapCommon.hh / FPGAModule::ReadModule.
    value = sum(client.read(0xE0100000 + (lane << 16)) << (8 * lane)
                for lane in range(4))
    firmware_id = (value >> 16) & 0xFFFF
    names = {
        0xF000: "MikumariClock-Root", 0xF100: "MikumariClock-Hub",
        0x60C4: "AMANEQ StrLrTdc", 0x61C4: "AMANEQ StrLrTdc-10G",
        0xC480: "AMANEQ StrHrTdc Base", 0xA000: "AMANEQ Skeleton",
        0x390A: "MikumariPrim-Ex", 0x390B: "MikumariSecond-Ex",
        0x413E: "CIRASAME Skeleton", 0x6041: "CIRASAME StrTdc",
        0x7041: "CIRASAME StrTdc-10G",
    }
    return (
        f"get_version {host}:\n"
        f"FW ID      : 0x{firmware_id:04x}\n"
        f"FW version : {(value >> 8) & 255}.{value & 255}\n"
        f"Firmware   : {names.get(firmware_id, 'Unknown firmware')}\n"
        f"Raw BCT    : 0x{value:08x}"
    )
