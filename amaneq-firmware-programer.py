#!/usr/bin/env python3
"""AMANEQ firmware programer. Python 3.10+, standard library only."""

import argparse
import gzip
import hashlib
import http.client
import socket
import ssl
import json
import plistlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SYNC = b"\xaa\x99\x55\x66"
MAX_IMAGE = 32 * 1024 * 1024
NETWORK_TIMEOUT = 45.0
TARGETS = ("amaneq-v1", "amaneq-v4", "hrtdc-mezzanine", "cirasame")
CIRASAME_REPOS = {
    "lrtdc": "CIRASAME-StrTdc",
    "lrtdc-10g": "CIRASAME-StrLRTDC-10G",
    "skeleton": "CIRASAME-Skeleton",
}
REPOS = {
    "lrtdc": "StrLrTdc",
    "hrtdc": "StrHrTdcBase",
    "lrtdc-10g": "StrLrTdc-10G",
    "mikumari": "MikuClockHub",
    "skeleton": "AMANEQ-Skeleton",
    "mezzanine": "MznStrHrTdc",
}
KNOWN_HS3 = {
    value.strip()
    for value in os.environ.get("AMANEQ_HS3_SERIALS", "").split(",")
    if value.strip()
}


class UserError(Exception):
    pass


def choose(items, label, display=str):
    if not items:
        raise UserError(f"No choices available: {label}")
    if not sys.stdin.isatty():
        raise UserError(
            f"{label}: specify options explicitly; interactive input unavailable."
        )
    print(f"\n{label}")
    for i, item in enumerate(items, 1):
        print(f"  {i}: {display(item)}")
    while True:
        answer = input("Number (q = cancel): ").strip()
        if answer.lower() == "q":
            raise UserError("Cancelled.")
        if answer.isdecimal() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]


def display_url(url):
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def fetch_bytes(url, headers=None, limit=MAX_IMAGE * 4):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise UserError("URL must use http:// or https://.")
    if parsed.username or parsed.password:
        raise UserError("URLs containing a username or password are not supported.")
    safe_url = display_url(url)
    try:
        request = urllib.request.Request(
            url, headers=headers or {"User-Agent": "AMANEQ-programmer/1"}
        )
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            if urllib.parse.urlsplit(response.geturl()).scheme not in ("http", "https"):
                raise UserError("Redirects to non-HTTP protocols are not supported.")
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    declared = int(declared)
                except ValueError as error:
                    raise UserError(
                        "The server returned an invalid Content-Length."
                    ) from error
                if declared < 0 or declared > limit:
                    raise UserError(
                        f"The download exceeds the maximum size of {limit} bytes."
                    )
            data = response.read(limit + 1)
            if len(data) > limit:
                raise UserError(
                    f"The download exceeds the maximum size of {limit} bytes."
                )
            if declared is not None and len(data) != declared:
                raise UserError(
                    "The download was interrupted or truncated. Please retry."
                )
            return data
    except urllib.error.HTTPError as error:
        hints = {
            400: "Check the URL and request parameters.",
            401: "Authentication is required. For the GitHub API, check GITHUB_TOKEN.",
            403: "Access was denied or the GitHub API rate limit was reached.",
            404: "The file, repository, or revision was not found. Check the URL.",
            429: "The rate limit was reached. Wait and retry.",
        }
        hint = hints.get(error.code, "The server returned an error. Wait and retry.")
        raise UserError(f"HTTP {error.code}: {hint} URL: {safe_url}") from error
    except (socket.timeout, TimeoutError) as error:
        raise UserError(
            f"Network timeout: no response within {NETWORK_TIMEOUT:g} seconds. Check the connection or increase --timeout.URL: {safe_url}"
        ) from error
    except urllib.error.URLError as error:
        reason = error.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            message = "Network timeout. Check the connection or increase --timeout."
        elif isinstance(reason, socket.gaierror):
            message = "DNS resolution failed. Check for an offline network, incorrect DNS settings, or an invalid URL hostname."
        elif isinstance(reason, ssl.SSLError):
            message = "TLS certificate verification failed. Check the system clock, certificates, and proxy settings."
        else:
            message = "Connection failed. Check the network connection, proxy, firewall, and download server."
        raise UserError(f"{message} URL: {safe_url}") from error
    except (http.client.HTTPException, ConnectionError, OSError) as error:
        raise UserError(
            f"The connection was interrupted or the transfer failed. Check the network and retry.URL: {safe_url}"
        ) from error


def request_json(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AMANEQ-programmer/1",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token and urllib.parse.urlparse(url).hostname == "api.github.com":
        headers["Authorization"] = f"Bearer {token}"
    data = fetch_bytes(url, headers, limit=16 * 1024 * 1024)
    try:
        return json.loads(data)
    except (ValueError, UnicodeDecodeError) as error:
        raise UserError(
            "The GitHub API returned invalid JSON. Check the proxy and repository URL."
        ) from error


class GitHub:
    def __init__(self, repo):
        if repo.startswith("https://github.com/"):
            repo = urllib.parse.urlparse(repo).path.strip("/").removesuffix(".git")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise UserError(
                "--repo must be owner/repository or its https://github.com URL."
            )
        self.repo = repo
        self.api = f"https://api.github.com/repos/{repo}"

    def get(self, suffix):
        return request_json(self.api + suffix)

    def pages(self, suffix, limit):
        result = []
        for page in range(1, (limit + 99) // 100 + 1):
            separator = "&" if "?" in suffix else "?"
            batch = self.get(f"{suffix}{separator}per_page=100&page={page}")
            result.extend(batch)
            if len(batch) < 100:
                break
        return result[:limit]

    def revision(self, ref):
        return self.get("/commits/" + urllib.parse.quote(ref, safe=""))["sha"]

    def files(self, commit):
        tree = self.get(f"/git/trees/{commit}?recursive=1")
        if tree.get("truncated"):
            raise UserError(
                "GitHub tree is truncated; refusing incomplete firmware listing."
            )
        return [
            entry
            for entry in tree["tree"]
            if entry["type"] == "blob"
            and entry["path"].lower().endswith((".bit", ".mcs"))
        ]

    def refs(self, limit):
        default = self.get("")["default_branch"]
        result = [(default, "Default branch (current files)")]
        if limit == 1:
            return result
        commits = {item["sha"]: item for item in self.pages("/commits", limit)}
        tags = {}
        for tag in self.pages("/tags", limit):
            sha = tag["commit"]["sha"]
            tags.setdefault(sha, []).append(tag["name"])
            if sha not in commits:
                commits[sha] = self.get("/commits/" + urllib.parse.quote(sha, safe=""))
        ordered = sorted(
            commits.values(),
            key=lambda item: item["commit"]["committer"]["date"],
            reverse=True,
        )
        for item in ordered[: limit - 1]:
            sha = item["sha"]
            info = item["commit"]
            names = tags.get(sha, [])
            ref = names[0] if names else sha
            label = info["committer"]["date"] + " " + info["message"].splitlines()[0]
            if names:
                label += " [tags: " + ", ".join(names) + "]"
            result.append((ref, label))
        return result


def repository(args):
    if args.target == "cirasame":
        if args.firmware not in CIRASAME_REPOS:
            raise UserError(
                "CIRASAME supports lrtdc, lrtdc-10g and skeleton profiles only."
            )
        owner = "spadi-alliance" if args.owner == "AMANEQ-official" else args.owner
        return GitHub(args.repo or f"{owner}/{CIRASAME_REPOS[args.firmware]}")
    if args.target == "hrtdc-mezzanine":
        if args.firmware != "hrtdc":
            raise UserError("HR-TDC mezzanine requires --firmware hrtdc.")
        name = REPOS["mezzanine"]
    else:
        name = REPOS[args.firmware]
    owner = (
        "spadi-alliance"
        if args.firmware == "skeleton" and args.owner == "AMANEQ-official"
        else args.owner
    )
    return GitHub(args.repo or f"{owner}/{name}")


def version_key(path):
    name = re.sub(r"\.(?:bit|mcs)$", "", Path(path).name, flags=re.IGNORECASE)
    match = re.search(r"-v([0-9A-Fa-f]+(?:\.[0-9A-Fa-f]+)*)", name)
    return tuple(int(part, 16) for part in match[1].split(".")) if match else ()


def filename_target(name):
    name = Path(name).name.lower()
    if name.startswith("cirasame-"):
        return "cirasame"
    if re.search(r"amaneq[-_]1[-_]", name):
        return "amaneq-v1"
    if re.search(r"amaneq[-_]4[-_]", name):
        return "amaneq-v4"
    if re.search(r"mzn[-_]strhrtdc", name):
        return "hrtdc-mezzanine"
    return None


def filename_family(name):
    name = Path(name).name.lower()
    if name.startswith("cirasame-"):
        if "skeleton" in name or name.startswith("cirasame-fw-"):
            return "skeleton"
        if "strtdc10g" in name:
            return "lrtdc-10g"
        if "strtdc" in name:
            return "lrtdc"
    if re.search(r"amaneq[-_]skeleton[-_]", name):
        return "skeleton"
    if "strlrtdc-10g" in name:
        return "lrtdc-10g"
    if "strlrtdc" in name:
        return "lrtdc"
    if "strhrtdc" in name:
        return "hrtdc"
    if re.search(r"amaneq[-_][14][-_]mch[-_]", name):
        return "mikumari"
    return None


def candidates(entries, args):
    return [
        item
        for item in entries
        if item["path"].lower().endswith("." + args.format)
        and (
            filename_target(item["path"]) == args.target
            or (
                args.firmware == "skeleton"
                and args.target in ("amaneq-v1", "amaneq-v4")
                and filename_family(item["path"]) == "skeleton"
            )
        )
        and (
            args.flash == "auto"
            or args.target != "hrtdc-mezzanine"
            or args.format == "bit"
            or args.flash.lower() in item["path"].lower()
        )
    ]


def resolve_artifact(args):
    github = repository(args)
    ref = args.ref or github.get("")["default_branch"]
    if args.choose_version:
        ref = choose(
            github.refs(args.history_limit),
            "Choose tag or commit",
            lambda x: f"{x[0]}  {x[1]}",
        )[0]
    commit = github.revision(ref)
    entries = github.files(commit)
    if args.artifact_path:
        selected = [item for item in entries if item["path"] == args.artifact_path]
        if len(selected) != 1:
            raise UserError(
                "--artifact-path is not a BIT/MCS blob in the selected revision."
            )
        item = selected[0]
        inferred = filename_target(item["path"])
        if inferred and inferred != args.target:
            raise UserError("Selected artifact filename does not match --target.")
    else:
        options = candidates(entries, args)
        if not options:
            raise UserError(
                "No matching firmware files. Use --ref/--repo or --artifact-path."
            )
        if not args.choose_version:
            best = max(version_key(item["path"]) for item in options)
            options = [item for item in options if version_key(item["path"]) == best]
        item = (
            options[0]
            if len(options) == 1
            else choose(options, "Choose firmware file", lambda x: x["path"])
        )
    return github, ref, commit, item


@dataclass
class Image:
    kind: str
    payload: bytes
    metadata: dict
    idcode: int | None


def parse_mcs(data):
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise UserError("MCS is not ASCII.") from error
    segments = []
    base = 0
    eof = False
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if eof:
            raise UserError(f"MCS data after EOF on line {number}.")
        try:
            if not line.startswith(":"):
                raise ValueError("missing colon")
            record = bytes.fromhex(line[1:])
            if len(record) < 5 or len(record) != record[0] + 5 or sum(record) % 256:
                raise ValueError("length/checksum")
            length, kind = record[0], record[3]
            address = int.from_bytes(record[1:3], "big")
            chunk = record[4 : 4 + length]
            if kind == 0:
                if base + address + length > MAX_IMAGE:
                    raise ValueError("image exceeds 32 MiB")
                if length:
                    segments.append((base + address, chunk))
            elif kind == 1:
                if length or address:
                    raise ValueError("invalid EOF")
                eof = True
            elif kind in (2, 4):
                if length != 2 or address:
                    raise ValueError("invalid extended address")
                base = int.from_bytes(chunk, "big") << (4 if kind == 2 else 16)
            elif kind in (3, 5):
                if length != 4 or address:
                    raise ValueError("invalid start address")
            else:
                raise ValueError("unsupported record")
        except ValueError as error:
            raise UserError(f"Invalid MCS line {number}: {error}") from error
    if not eof or not segments:
        raise UserError("MCS requires data records and EOF.")
    segments.sort(key=lambda item: item[0])
    end = 0
    for address, chunk in segments:
        if address < end:
            raise UserError("Overlapping MCS records.")
        end = address + len(chunk)
    payload = bytearray(b"\xff") * end
    for address, chunk in segments:
        payload[address : address + len(chunk)] = chunk
    return bytes(payload)


def parse_bit(data):
    # Xilinx .bit header: magic, marker, a/b/c/d strings, e + uint32 payload length.
    if (
        len(data) < 16
        or data[:2] != b"\x00\x09"
        or data[2:11] != b"\x0f\xf0\x0f\xf0\x0f\xf0\x0f\xf0\x00"
    ):
        raise UserError(
            "Unrecognized file content; expected Xilinx BIT or Intel HEX MCS."
        )
    if data[11:13] != b"\x00\x01":
        raise UserError("Invalid BIT header marker.")
    offset = 13
    meta = {}
    for field in ("a", "b", "c", "d", "e"):
        if offset >= len(data) or data[offset] != ord(field):
            raise UserError("Invalid BIT header field.")
        offset += 1
        width = 4 if field == "e" else 2
        if offset + width > len(data):
            raise UserError("Truncated BIT header.")
        size = int.from_bytes(data[offset : offset + width], "big")
        offset += width
        if offset + size > len(data):
            raise UserError("Truncated BIT payload/header.")
        value = data[offset : offset + size]
        offset += size
        if field == "e":
            if offset != len(data):
                raise UserError("Trailing bytes in BIT file.")
            return value, meta
        meta[{"a": "design", "b": "part", "c": "date", "d": "time"}[field]] = (
            value.rstrip(b"\0").decode("ascii", errors="replace")
        )


def config_idcode(payload):
    offset = payload.find(SYNC)
    if offset < 0:
        raise UserError("Xilinx configuration sync word not found.")
    offset += 4
    previous_count = 0
    while offset + 4 <= len(payload):
        word = struct.unpack_from(">I", payload, offset)[0]
        offset += 4
        kind = word >> 29
        if kind == 1:
            count = word & 0x7FF
            register = (word >> 13) & 0x3FFF
            previous_count = (word >> 27) & 3
            if previous_count == 2 and register == 12 and count == 1:
                if offset + 4 > len(payload):
                    raise UserError("Truncated IDCODE packet.")
                return struct.unpack_from(">I", payload, offset)[0]
        elif kind == 2:
            count = word & 0x7FFFFFF
        else:
            break
        offset += count * 4
    raise UserError(
        "Configuration IDCODE not found; cannot validate FPGA compatibility."
    )


def inspect_file(path):
    data = Path(path).read_bytes()
    if len(data) > MAX_IMAGE * 4:
        raise UserError("Firmware file too large.")
    if data.lstrip().startswith(b":"):
        payload = parse_mcs(data)
        kind = "mcs"
        meta = {}
    else:
        payload, meta = parse_bit(data)
        kind = "bit"
    return Image(kind, payload, meta, config_idcode(payload))


def validate_firmware_format(image, args):
    if image.kind not in ("mcs", "bit"):
        raise UserError("Firmware format must be MCS or BIT.")


def download(args):
    if getattr(args, "url", None):
        return download_url(args)
    github, ref, commit, item = resolve_artifact(args)
    url = (
        f"https://raw.githubusercontent.com/{github.repo}/{commit}/"
        + urllib.parse.quote(item["path"], safe="/")
    )
    data = fetch_bytes(url)
    if (
        len(data) != item["size"]
        or hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        != item["sha"]
    ):
        raise UserError("Downloaded file does not match GitHub blob size/hash.")
    destination = (
        Path(args.download_dir)
        / github.repo.replace("/", "_")
        / commit[:12]
        / Path(item["path"]).name
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_bytes(data)
        image = inspect_file(temporary)
        validate_firmware_format(image, args)
        if image.kind != Path(item["path"]).suffix.lower()[1:]:
            raise UserError("GitHub filename format does not match file content.")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    provenance = {
        "repo": github.repo,
        "ref": ref,
        "commit": commit,
        "path": item["path"],
        "blob_sha1": item["sha"],
        "sha256": hashlib.sha256(data).hexdigest(),
        "url": url,
    }
    destination.with_suffix(destination.suffix + ".source.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    print(f"Downloaded and verified: {destination}")
    return destination


def download_url(args):
    data = fetch_bytes(args.url)
    digest = hashlib.sha256(data).hexdigest()
    if args.sha256 and digest.lower() != args.sha256.lower():
        raise UserError(
            "The download does not match the expected SHA256. Saving and programming were aborted."
        )
    parsed = urllib.parse.urlsplit(args.url)
    basename = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1]) or "firmware"
    basename = re.sub(r"[^A-Za-z0-9_.-]", "_", basename)[:160].strip(".") or "firmware"
    destination_dir = Path(args.download_dir) / "direct-url" / digest[:12]
    destination_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination_dir, suffix=".tmp", delete=False
    ) as temporary:
        temporary.write(data)
        temp_path = Path(temporary.name)
    try:
        try:
            image = inspect_file(temp_path)
            validate_firmware_format(image, args)
        except UserError as error:
            raise UserError(
                f"The downloaded content is not valid BIT/MCS firmware. Use a direct file URL rather than an HTML page. Details: {error}"
            ) from error
        inferred = filename_target(basename)
        family = filename_family(basename)
        if inferred and inferred != args.target:
            raise UserError(
                f"The URL filename indicates {inferred}, but the selected target is {args.target}."
            )
        if family and family != args.firmware:
            raise UserError(
                f"The URL filename indicates {family}, but the selected firmware family is {args.firmware}."
            )
        stem = (
            Path(basename).stem
            if Path(basename).suffix.lower() in (".bit", ".mcs")
            else basename
        )
        destination = destination_dir / (stem + "." + image.kind)
        temp_path.replace(destination)
    finally:
        temp_path.unlink(missing_ok=True)
    provenance = {
        "url": display_url(args.url),
        "sha256": digest,
        "format": image.kind,
        "expected_sha256_verified": bool(args.sha256),
        "source": "direct-url",
    }
    destination.with_suffix(destination.suffix + ".source.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    print(f"Downloaded; content validated ({image.kind}): {destination}")
    print(f"SHA256: {digest}")
    return destination


def loader_path(args):
    if args.loader:
        path = shutil.which(args.loader) or args.loader
    else:
        bundled = ROOT / "installed/ucrt64/bin/openFPGALoader.exe"
        path = (
            str(bundled)
            if os.name == "nt" and bundled.exists()
            else shutil.which("openFPGALoader")
        )
    if not path or not Path(path).is_file():
        raise UserError("openFPGALoader not found; use --loader.")
    return str(Path(path).resolve())


def run_loader(loader, arguments, env=None):
    command = [loader, *map(str, arguments)]
    print(">", subprocess.list2cmdline(command), flush=True)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    output = []
    for line in process.stdout:
        print(line, end="", flush=True)
        output.append(line)
    code = process.wait()
    if code:
        raise UserError(f"openFPGALoader failed (exit {code}).")
    return "".join(output)


def scan_cables(args):
    loader = loader_path(args)
    supported = subprocess.run(
        [loader, "--list-cables"], capture_output=True, text=True, check=True
    ).stdout
    devices = []
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["/usr/sbin/ioreg", "-a", "-r", "-c", "IOUSBHostDevice"],
                capture_output=True,
                timeout=30,
                check=True,
            )
            roots = plistlib.loads(result.stdout)
        except (
            OSError,
            subprocess.SubprocessError,
            plistlib.InvalidFileException,
            ValueError,
        ) as error:
            raise UserError(f"macOS USB enumeration failed: {error}") from error
        records = []

        def visit(nodes):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                vid = node.get("idVendor")
                pid = node.get("idProduct")
                if (
                    isinstance(vid, int)
                    and isinstance(pid, int)
                    and (
                        (vid, pid) == (0x0403, 0x6014)
                        or vid == 0x03FD
                        and pid in (0x0007, 0x0008, 0x0009, 0x000D, 0x0013)
                    )
                ):
                    serial = str(node.get("USB Serial Number", ""))
                    records.append(
                        {
                            "id": f"USB\\VID_{vid:04X}&PID_{pid:04X}\\{serial}",
                            "description": str(node.get("USB Product Name", "")),
                            "driver": "macOS USB (access checked at JTAG)",
                            "status": "OK",
                        }
                    )
                visit(node.get("IORegistryEntryChildren", []))

        if not isinstance(roots, list):
            raise UserError("macOS USB enumeration returned an invalid device tree.")
        visit(roots)

    elif os.name == "nt":
        # Fixed read-only PowerShell query. User input is never inserted in shell code.
        query = r"""$ErrorActionPreference='Stop'; $items=@(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -match '^USB\\VID_(0403&PID_6014|03FD&PID_(0007|0008|0009|000D|0013))\\'}); $out=@(foreach($d in $items){$service=$null;$desc=$null;try{$service=(Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName DEVPKEY_Device_Service -ErrorAction Stop).Data}catch{};try{$desc=(Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName DEVPKEY_Device_BusReportedDeviceDesc -ErrorAction Stop).Data}catch{};[pscustomobject]@{id=$d.InstanceId;description=$desc;driver=$service;status=$d.Status}});ConvertTo-Json -InputObject $out -Compress"""
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", query],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise UserError("Windows USB enumeration failed: " + result.stderr.strip())
        records = json.loads(result.stdout or "[]")
    else:
        records = []
        for directory in Path("/sys/bus/usb/devices").glob("*"):
            try:
                vid = (directory / "idVendor").read_text().strip().upper()
                pid = (directory / "idProduct").read_text().strip().upper()
                if (vid, pid) != ("0403", "6014") and not (
                    vid == "03FD" and pid in ("0007", "0008", "0009", "000D", "0013")
                ):
                    continue
                serial = (
                    (directory / "serial").read_text().strip()
                    if (directory / "serial").exists()
                    else ""
                )
                product = (
                    (directory / "product").read_text().strip()
                    if (directory / "product").exists()
                    else ""
                )
                busdev = (
                    str(int((directory / "busnum").read_text()))
                    + ":"
                    + str(int((directory / "devnum").read_text()))
                )
                records.append(
                    {
                        "id": f"USB\\VID_{vid}&PID_{pid}\\{serial}",
                        "description": product,
                        "driver": "Linux USB (permissions checked at JTAG)",
                        "status": "OK",
                        "busdev": busdev,
                    }
                )
            except (OSError, ValueError):
                continue
    for item in records:
        match = re.match(
            r"USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})\\(.*)", item["id"], re.I
        )
        if not match:
            continue
        vid, pid, serial = match.groups()
        desc = item.get("description") or ""
        cable = None
        kind = "FT232H candidate (HS2/HS3/etc.)"
        if vid.upper() == "03FD":
            kind = "Xilinx Platform Cable candidate"
            if re.search(r"^xilinxPlatformCableUsb\s", supported, re.M):
                cable = "xilinxPlatformCableUsb"
        elif serial in KNOWN_HS3 or re.search(r"HS[- ]?3", desc, re.I):
            cable = "digilent_hs3"
            kind = "Digilent JTAG-HS3"
        if args.cable == "hs3" and vid.upper() == "0403":
            cable = "digilent_hs3"
            kind = "HS3 (user selected)"
        if args.cable == "xilinx" and vid.upper() == "03FD":
            cable = (
                "xilinxPlatformCableUsb"
                if "xilinxPlatformCableUsb" in supported
                else None
            )
        driver_ok = (
            sys.platform == "darwin"
            or os.name != "nt"
            or item["driver"]
            in (
                "WinUSB",
                "libusbK",
                "libusb0",
            )
        )
        devices.append(
            {
                **item,
                "serial": serial,
                "vidpid": f"{vid}:{pid}",
                "type": kind,
                "cable": cable,
                "ready": bool(cable and driver_ok and item["status"] == "OK"),
            }
        )
    return devices


def show_cable_candidates(devices):
    print("Connected cable candidates:", file=sys.stderr)
    for device in devices:
        serial = device.get("serial") or "<not reported>"
        print(
            f"  Serial: {serial} | Type: {device.get('type', 'unknown')} | USB: {device.get('vidpid', 'unknown')}",
            file=sys.stderr,
        )


def select_cable(args):
    all_devices = scan_cables(args)
    if len(all_devices) > 1 and not args.serial:
        show_cable_candidates(all_devices)
        raise UserError(
            "Multiple cables found. Specify --serial; interactive cable selection is disabled."
        )
    devices = all_devices
    if args.serial:
        devices = [d for d in devices if d["serial"] == args.serial]
    if args.cable == "hs3":
        devices = [d for d in devices if d["vidpid"].upper() == "0403:6014"]
    elif args.cable == "xilinx":
        devices = [d for d in devices if d["vidpid"].upper().startswith("03FD:")]
    if not devices:
        raise UserError(
            "No matching connected cable. WSL needs usbipd attach; containers need USB passthrough."
        )
    if len(devices) > 1:
        show_cable_candidates(devices)
        raise UserError(
            "The cable selection is not unique. Disconnect duplicate devices; no programming performed."
        )
    device = devices[0]
    if not device["cable"] and device["vidpid"].upper() == "0403:6014":
        if args.yes:
            raise UserError(
                "FT232H model ambiguous; use --cable hs3 only after checking hardware."
            )
        choice = choose(
            ["HS3", "Cancel"],
            "USB ID is shared. Is the selected device physically an HS3?",
        )
        if choice != "HS3":
            raise UserError("Cancelled.")
        device["cable"] = "digilent_hs3"
        device["ready"] = os.name != "nt" or device["driver"] in (
            "WinUSB",
            "libusbK",
            "libusb0",
        )
    if not device["cable"]:
        raise UserError(
            "This openFPGALoader build does not support the detected cable. Use a supported Linux build or Vivado."
        )
    if not device["ready"]:
        raise UserError(
            f"USB driver {device['driver']} is not ready for libusb. No driver changes performed."
        )
    selector = ["-c", device["cable"]]
    if os.name != "nt" and device["cable"] == "xilinxPlatformCableUsb":
        if sum(d["vidpid"].upper().startswith("03FD:") for d in all_devices) != 1:
            raise UserError(
                "Xilinx driver does not honor bus/serial selection; connect exactly one Xilinx cable."
            )
        vid, pid = device["vidpid"].split(":")
        selector += ["--vid", "0x" + vid, "--pid", "0x" + pid]
        if args.probe_firmware:
            selector += ["--probe-firmware", args.probe_firmware]
    elif sys.platform == "darwin":
        if not device["serial"]:
            raise UserError(
                "macOS FTDI selection requires a USB serial number; nothing written."
            )
        selector += ["--ftdi-serial", device["serial"]]
    elif os.name != "nt":
        selector += ["--busdev-num", device["busdev"]]
    elif (
        device["cable"] == "digilent_hs3"
        and device["serial"]
        and "&" not in device["serial"]
    ):
        selector += ["--ftdi-serial", device["serial"]]
    else:
        raise UserError(
            "Cannot uniquely select this Windows cable by serial; refusing automatic programming."
        )
    return device, selector


def environment(args):
    env = os.environ.copy()
    if os.name == "nt":
        directories = [
            args.cygpath_dir,
            env.get("AMANEQ_CYGPATH_DIR"),
            r"C:\Program Files\Git\usr\bin",
            str(ROOT / "tools/cygwin/bin"),
        ]
        for directory in directories:
            if directory and (Path(directory) / "cygpath.exe").exists():
                env["PATH"] = str(directory) + os.pathsep + env.get("PATH", "")
                break
        if not shutil.which("cygpath", path=env.get("PATH")):
            raise UserError(
                "Windows flash mode requires cygpath.exe. Add it to PATH or use --cygpath-dir; BIT mode does not need it."
            )
    return env


def bridge_file(args):
    if args.bridge:
        path = Path(args.bridge)
    else:
        locations = [
            ROOT / "installed/ucrt64/share/openFPGALoader",
            Path(loader_path(args)).parent.parent / "share/openFPGALoader",
            Path("/usr/share/openFPGALoader"),
            Path("/usr/local/share/openFPGALoader"),
        ]
        path = next(
            (
                directory / name
                for directory in locations
                for name in (
                    "spiOverJtag_xc7k160tffg676.bit.gz",
                    "spiOverJtag_xc7k160tffg676.bit",
                )
                if (directory / name).is_file()
            ),
            locations[0] / "spiOverJtag_xc7k160tffg676.bit.gz",
        )
    if not path.is_file():
        raise UserError(
            "SPI-over-JTAG bridge not found; use --bridge for XC7K160T FFG676."
        )
    if path.suffix == ".gz":
        destination = ROOT / "firmware/cache/spiOverJtag_xc7k160tffg676.bit"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(gzip.decompress(path.read_bytes()))
        path = destination
    image = inspect_file(path)
    if image.kind != "bit" or image.idcode & 0x0FFFFFFF != 0x0364C093:
        raise UserError("Bridge is not a BIT for XC7K160T.")
    return path.resolve()


def flash_identity(output):
    flash = re.search(r"Detected:\s*(.+?)\s+size:\s*(\d+)Mb", output, re.I)
    jedec = re.search(r"JEDEC ID:\s*0x([0-9a-f]+)", output, re.I)
    if not flash or not jedec:
        raise UserError(
            "Flash model, capacity and JEDEC ID must all be detected; refusing erase."
        )
    model = flash[1].lower()
    capacity = int(flash[2]) * 1024 * 1024 // 8
    identities = {
        0x012018: ("s25fl128s", 16, "s25fl128s"),
        0x20BB19: ("mt25qu256", 32, "(?:n25q256|mt25q.*256)"),
        0x20BB18: ("n25q128", 16, "(?:n25q128|mt25q.*128)"),
        0x20BA18: ("n25q128", 16, "(?:n25q128|mt25q.*128)"),
    }
    identity = identities.get(int(jedec[1], 16))
    if (
        not identity
        or capacity != identity[1] * 1024 * 1024
        or not re.search(identity[2], model)
    ):
        raise UserError(
            f"Unexpected/contradictory flash: {model}, JEDEC {jedec[1]}; refusing erase."
        )
    return identity[0], model, capacity


def detect_mezzanine_flash(args, selected_cable=None):
    if args.firmware != "hrtdc":
        raise UserError("HR-TDC mezzanine requires --firmware hrtdc.")
    device, selector = selected_cable or select_cable(args)
    loader = loader_path(args)
    print("Detecting mezzanine flash before selecting the download.")
    print(
        "The SPI bridge will temporarily replace the SRAM configuration; flash will not be erased."
    )
    detected = run_loader(loader, selector + ["--detect"])
    ids = re.findall(r"idcode\s+0x([0-9a-f]+)", detected, re.I)
    if len(ids) != 1 or int(ids[0], 16) & 0x0FFFFFFF != 0x0364C093:
        raise UserError(
            "JTAG must contain exactly one XC7K160T before probing mezzanine flash."
        )
    env = environment(args)
    bridge = bridge_file(args)
    spi = selector + ["--fpga-part", "xc7k160tffg676", "-B", str(bridge)]
    with tempfile.TemporaryDirectory(prefix="amaneq-probe-") as temporary:
        output = run_loader(
            loader,
            spi
            + ["--dump-flash", "--file-size", "1", str(Path(temporary) / "probe.bin")],
            env,
        )
        identity, model, capacity = flash_identity(output)
    if identity not in ("mt25qu256", "n25q128"):
        raise UserError(
            f"Detected {model}, which is not a supported HR-TDC mezzanine flash. No erase performed."
        )
    print(
        f"Automatically selected mezzanine firmware variant: {identity} ({capacity//(1024*1024)} MiB)."
    )
    return identity, (device, selector)


def program(args):
    selected_cable = select_cable(args)
    repository_download = (
        not args.file
        and not getattr(args, "url", None)
        and (args.latest or args.choose_version or args.ref)
    )
    if (
        repository_download
        and args.target == "hrtdc-mezzanine"
        and args.format == "mcs"
        and args.flash == "auto"
    ):
        args.flash, selected_cable = detect_mezzanine_flash(args, selected_cable)
    if args.file:
        path = Path(args.file).resolve()
    elif getattr(args, "url", None) or args.latest or args.choose_version or args.ref:
        path = download(args).resolve()
    else:
        path = choose(
            local_files(args), "Choose downloaded/local firmware", str
        ).resolve()
    image = inspect_file(path)
    validate_firmware_format(image, args)
    inferred = filename_target(path.name)
    if inferred and inferred != args.target:
        raise UserError(
            f"Filename indicates {inferred}; selected target is {args.target}."
        )
    family = filename_family(path.name)
    if family and family != args.firmware:
        raise UserError(
            f"Filename indicates {family}; selected firmware is {args.firmware}."
        )
    if args.target == "hrtdc-mezzanine" and args.firmware != "hrtdc":
        raise UserError("HR-TDC mezzanine requires --firmware hrtdc.")
    if (
        image.metadata.get("part")
        and image.metadata["part"].lower().removeprefix("xc") != "7k160tffg676"
    ):
        raise UserError("BIT package/part is not XC7K160T FFG676.")
    if image.idcode & 0x0FFFFFFF != 0x0364C093:
        raise UserError("Firmware is not for XC7K160T.")
    device, selector = selected_cable or select_cable(args)
    loader = loader_path(args)
    print(
        f"Target: {args.target}; firmware: {args.firmware}; format from content: {image.kind}; cable: {device['serial']}"
    )
    print(
        "AMANEQ v1/v4, mezzanine and CIRASAME share FPGA ID; board identity cannot be inferred from JTAG alone."
    )
    if not args.yes and input(
        "Program selected target? [y/N] "
    ).strip().lower() not in ("y", "yes"):
        raise UserError("Cancelled.")
    detected = run_loader(loader, selector + ["--detect"])
    ids = re.findall(r"idcode\s+0x([0-9a-f]+)", detected, re.I)
    if len(ids) != 1 or int(ids[0], 16) & 0x0FFFFFFF != image.idcode & 0x0FFFFFFF:
        raise UserError(
            "JTAG must contain exactly one matching XC7K160T; nothing written."
        )
    logs = Path(args.log_dir)
    logs.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report = {
        "file": str(path),
        "target": args.target,
        "format": image.kind,
        "cable": device,
        "firmware_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "result": "started",
    }
    try:
        if image.kind == "bit":
            output = run_loader(
                loader, selector + ["--file-type", "bit", "-m", str(path)]
            )
            if not re.search(r"\bdone\s+1\b", output, re.I):
                raise UserError(
                    "BIT command returned success but DONE=1 was not observed."
                )
            report["result"] = "BIT loaded; DONE=1"
        else:
            env = environment(args)
            bridge = bridge_file(args)
            spi = selector + ["--fpga-part", "xc7k160tffg676", "-B", str(bridge)]
            with tempfile.TemporaryDirectory(prefix="amaneq-") as tmp:
                probe = Path(tmp) / "probe.bin"
                output = run_loader(
                    loader, spi + ["--dump-flash", "--file-size", "1", str(probe)], env
                )
                identity, model, capacity = flash_identity(output)
                expected = (
                    "s25fl128s" if args.target != "hrtdc-mezzanine" else args.flash
                )
                if args.target == "hrtdc-mezzanine" and expected == "auto":
                    expected = (
                        identity if identity in ("mt25qu256", "n25q128") else None
                    )
                if (
                    not expected
                    or expected != identity
                    or len(image.payload) > capacity
                ):
                    raise UserError(
                        f"Unexpected/undersized flash: {model}; expected {expected}; no erase performed."
                    )
                named_flash = next(
                    (
                        name
                        for name in ("mt25qu256", "n25q128")
                        if name in path.name.lower()
                    ),
                    None,
                )
                if named_flash and named_flash != expected:
                    raise UserError(
                        "MCS filename flash variant differs from detected flash."
                    )
                report["flash"] = model
                safe_serial = re.sub(r"[^A-Za-z0-9_.-]", "_", device["serial"] or "usb")
                backup = logs / f"{stamp}-{safe_serial}-flash-backup.bin"
                run_loader(
                    loader,
                    spi + ["--dump-flash", "--file-size", str(capacity), str(backup)],
                    env,
                )
                if backup.stat().st_size != capacity:
                    raise UserError("Incomplete flash backup; refusing erase.")
                report["backup"] = str(backup)
                run_loader(loader, spi + ["--file-type", "mcs", "-f", str(path)], env)
                readback = logs / f"{stamp}-readback.bin"
                run_loader(
                    loader,
                    spi
                    + [
                        "--dump-flash",
                        "--file-size",
                        str(len(image.payload)),
                        str(readback),
                    ],
                    env,
                )
                actual = readback.read_bytes()
                if actual != image.payload:
                    raise UserError(
                        "Flash readback mismatch. Keep backup/logs; flash boot is not verified."
                    )
                report["readback_sha256"] = hashlib.sha256(actual).hexdigest()
                report["result"] = (
                    "MCS written; every byte verified; power-cycle boot not tested"
                )
                print(
                    "Flash content verified. Power-cycle required to verify persistent boot."
                )
                print(
                    "SPI bridge remains in SRAM; no automatic power control or driver changes."
                )
    except Exception as error:
        report["result"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        (logs / f"{stamp}-result.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    print(report["result"])


def local_files(args):
    roots = [ROOT / "firmware", Path(args.download_dir)]
    result = set()
    for root in roots:
        if root.exists():
            for path in root.rglob("*"):
                if (
                    path.suffix.lower() in (".bit", ".mcs")
                    and "spiOverJtag" not in path.name
                ):
                    result.add(path.resolve())
    return sorted(result)


def add_common(parser):
    parser.add_argument("--loader", help="Path to openFPGALoader executable")
    parser.add_argument(
        "--cable",
        choices=("auto", "hs3", "xilinx"),
        default="auto",
        help="Cable model; select hs3 explicitly when an FT232H description is ambiguous",
    )
    parser.add_argument("--serial", help="Select a cable serial explicitly")
    parser.add_argument(
        "--probe-firmware",
        help="Xilinx USB cable firmware supplied by the user (Linux only)",
    )
    parser.add_argument(
        "--firmware",
        choices=("lrtdc", "hrtdc", "lrtdc-10g", "mikumari", "skeleton"),
        default="lrtdc",
        help="Firmware family; MCS and BIT programming are supported",
    )
    parser.add_argument(
        "--target",
        choices=TARGETS,
        default="amaneq-v4",
        help="Physical target; revision cannot be inferred from the FPGA ID",
    )
    parser.add_argument(
        "--format",
        choices=("mcs", "bit"),
        default="mcs",
        help="Download format; local files are identified by contents",
    )
    parser.add_argument(
        "--owner", default="AMANEQ-official", help="GitHub organization/user"
    )
    parser.add_argument(
        "--url",
        help="Direct HTTP(S) URL to BIT/MCS firmware; format is detected from content",
    )
    parser.add_argument(
        "--sha256",
        help="Expected SHA256 for a direct URL download (64 hex digits); abort on mismatch",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=45,
        help="Network inactivity timeout in seconds",
    )
    parser.add_argument(
        "--repo",
        help="Override GitHub owner/repository or https://github.com/owner/repository",
    )
    parser.add_argument("--ref", help="Git branch, tag, or commit SHA")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Newest named firmware in default branch (hex version ordering)",
    )
    parser.add_argument(
        "--choose-version",
        action="store_true",
        help="Interactively select tag/commit, then file",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=10,
        help="Maximum total history choices, including the current branch; newest revisions first",
    )
    parser.add_argument(
        "--artifact-path", help="Exact repository BIT/MCS path (for custom naming)"
    )
    parser.add_argument(
        "--flash",
        choices=("auto", "s25fl128s", "mt25qu256", "n25q128"),
        default="auto",
        help="Flash variant; program probes mezzanine hardware before a GitHub MCS download",
    )
    parser.add_argument(
        "--download-dir",
        default=str(ROOT / "firmware/downloads"),
        help="Directory for validated downloads and source metadata",
    )
    parser.add_argument(
        "--log-dir",
        default=str(ROOT / "logs"),
        help="Directory for flash backups, readbacks, and result JSON",
    )
    parser.add_argument("--bridge", help="XC7K160T SPI-over-JTAG BIT/bit.gz")
    parser.add_argument(
        "--cygpath-dir", help="Windows directory containing cygpath.exe"
    )
    parser.add_argument(
        "--file", help="Existing local firmware file; content determines BIT/MCS"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip final programming confirmation; does not guess ambiguous hardware",
    )


def main(argv=None):
    global NETWORK_TIMEOUT
    parser = argparse.ArgumentParser(
        description="AMANEQ: detect cables, download firmware, and program devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  ./amaneq-firmware-programer.py scan
  ./amaneq-firmware-programer.py download --latest --target amaneq-v4 --format mcs
  ./amaneq-firmware-programer.py download --url https://server.example/firmware.mcs
  ./amaneq-firmware-programer.py program --url https://server.example/firmware.bit --firmware skeleton --serial SERIAL_FROM_SCAN
  ./amaneq-firmware-programer.py program --file firmware/amaneq-4-strlrtdc-v2.A.mcs
  ./amaneq-firmware-programer.py program --choose-version --firmware hrtdc --target hrtdc-mezzanine

Run without arguments for interactive mode. Use COMMAND --help for details.
BIT/MCS format is detected from content. JTAG ID alone cannot identify the board revision.""",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in (
        "scan",
        "inspect",
        "local",
        "versions",
        "download",
        "program",
        "wizard",
    ):
        descriptions = {
            "scan": "List connected cables and drivers without programming",
            "inspect": "Inspect firmware contents without programming",
            "local": "List locally saved firmware files",
            "versions": "List GitHub tags and commits",
            "download": "Download from GitHub or a direct URL without programming",
            "program": "Program selected firmware using openFPGALoader",
            "wizard": "Interactively select hardware, firmware, and cable",
        }
        p = sub.add_parser(
            command,
            help=descriptions[command],
            description=descriptions[command],
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        add_common(p)
    if argv is None:
        argv = sys.argv[1:]
    args = parser.parse_args(argv or ["wizard"])
    if not 0 < args.timeout <= 3600:
        raise UserError("--timeout must be greater than 0 and at most 3600 seconds.")
    NETWORK_TIMEOUT = args.timeout
    if args.url and (
        args.file
        or args.repo
        or args.ref
        or args.latest
        or args.choose_version
        or args.artifact_path
    ):
        raise UserError(
            "--url cannot be combined with --file/--repo/--ref/--latest/--choose-version/--artifact-path."
        )
    if args.url and args.command not in ("download", "program", "wizard"):
        raise UserError("--url is only supported by download/program/wizard.")
    if args.sha256 and (
        not args.url or not re.fullmatch(r"[0-9a-fA-F]{64}", args.sha256)
    ):
        raise UserError("--sha256 requires --url and exactly 64 hexadecimal digits.")
    if args.history_limit < 1 or args.history_limit > 1000:
        raise UserError("--history-limit must be 1..1000.")
    if args.latest and (args.ref or args.choose_version):
        raise UserError("--latest cannot be combined with --ref or --choose-version.")
    if args.file and (args.latest or args.ref or args.choose_version):
        raise UserError("--file cannot be combined with GitHub source selectors.")
    if args.command == "wizard":
        select_cable(args)
        args.target = choose(list(TARGETS), "Choose hardware target")
        args.firmware = (
            "hrtdc"
            if args.target == "hrtdc-mezzanine"
            else choose(
                ["lrtdc", "hrtdc", "lrtdc-10g", "mikumari", "skeleton"],
                "Choose firmware family",
            )
        )
        source = (
            "Direct URL"
            if args.url
            else choose(
                [
                    "Local file",
                    "Latest GitHub firmware",
                    "Historical GitHub firmware",
                    "Direct URL",
                ],
                "Choose firmware source",
            )
        )
        if source == "Direct URL":
            if not args.url:
                args.url = input("File HTTP(S) URL: ").strip()
        elif source == "Local file":
            args.file = str(choose(local_files(args), "Choose local firmware"))
        else:
            args.format = choose(["mcs", "bit"], "Choose download format")
            args.latest = source == "Latest GitHub firmware"
            args.choose_version = not args.latest
        program(args)
    elif args.command == "scan":
        print(json.dumps(scan_cables(args), indent=2))
    elif args.command == "inspect":
        if not args.file:
            raise UserError("inspect requires --file.")
        image = inspect_file(args.file)
        print(
            json.dumps(
                {
                    "format": image.kind,
                    "payload_bytes": len(image.payload),
                    "idcode": hex(image.idcode),
                    "metadata": image.metadata,
                    "filename_target": filename_target(args.file),
                },
                indent=2,
            )
        )
    elif args.command == "local":
        for path in local_files(args):
            print(path)
    elif args.command == "versions":
        github = repository(args)
        if args.ref:
            for item in candidates(github.files(github.revision(args.ref)), args):
                print(item["path"])
        else:
            for ref, label in github.refs(args.history_limit):
                print(ref, label)
    elif args.command == "download":
        download(args)
    elif args.command == "program":
        program(args)


if __name__ == "__main__":
    if os.name == "nt":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        main()
    except FileNotFoundError as error:
        print(f"ERROR: File or executable not found: {error.filename}", file=sys.stderr)
        sys.exit(1)
    except PermissionError as error:
        print(
            f"ERROR: Access denied to a file or USB device: {error.filename}",
            file=sys.stderr,
        )
        sys.exit(1)
    except (KeyError, TypeError) as error:
        print(
            f"ERROR: Unexpected API response or device information format: {error}",
            file=sys.stderr,
        )
        sys.exit(1)
    except (
        UserError,
        OSError,
        ValueError,
        urllib.error.URLError,
        subprocess.SubprocessError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print("Cancelled.", file=sys.stderr)
        sys.exit(130)
