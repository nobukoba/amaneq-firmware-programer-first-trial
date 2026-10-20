#!/usr/bin/env python3
"""Build a native Windows x64 ZIP or Linux x86_64 tar.gz desktop bundle."""

import argparse
import ast
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import urllib.error
import urllib.request

NAME = "amaneq-firmware-programer"
LOADER_REPOSITORY = "https://github.com/nobukoba/openFPGALoader"
LOADER_COMMIT = "bf2b52916e7b6216ba1cc0b30933827d7735b05d"
WINDOWS_LOADER_COMMIT = "3e5727bc1126307a0838d62f21971a2fa8f6a12f"
BRIDGE = "spiOverJtag_xc7k160tffg676.bit"


CYGWIN_MIRRORS = (
    "https://mirrors.dotsrc.org/cygwin/",
    "https://cygwin.osuosl.org/",
    "https://mirrors.kernel.org/sourceware/cygwin/",
)


def download_cygwin(path, size_limit):
    """Try official HTTPS mirrors on transport failure; keep content checks separate."""
    errors = []
    for base in CYGWIN_MIRRORS:
        url = base + path
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read(size_limit + 1)
        except (urllib.error.URLError, OSError) as error:
            errors.append(f"{url}: {error}")
            print(f"Cygwin mirror unavailable: {url}: {error}", flush=True)
            continue
        if len(data) > size_limit:
            raise ValueError(f"Cygwin download exceeds size limit: {url}")
        return data, url
    raise RuntimeError("All Cygwin mirrors failed: " + "; ".join(errors))


def stage_cygwin(cygwin, notices):
    """Ship the exact installed runtime source, checked against repository metadata."""
    cygwin = cygwin.resolve()
    environment = os.environ.copy()
    environment["PATH"] = str(cygwin) + os.pathsep + environment.get("PATH", "")
    packages = subprocess.check_output(
        [str(cygwin / "cygcheck.exe"), "-c", "cygwin", "libiconv2", "libintl8"],
        text=True,
        env=environment,
        timeout=30,
    )
    metadata_bytes, _ = download_cygwin("x86_64/setup.ini", 20_000_000)
    metadata = metadata_bytes.decode("utf-8")
    sources = []
    for package in ("cygwin", "libiconv2", "libintl8"):
        match = re.search(r"(?m)^" + package + r"\s+(\S+)\s+OK", packages)
        if not match:
            raise ValueError(f"Cannot identify the installed {package} package.")
        version = match.group(1)
        section = re.search(r"(?ms)^@ " + package + r"\n(.*?)(?=^@ |\Z)", metadata)
        if not section:
            raise ValueError(f"Source metadata is missing for {package}.")
        record = re.search(
            r"(?ms)^version: " + re.escape(version) + r"\n(.*?)(?=^version:|\Z)",
            section.group(1),
        )
        source = (
            re.search(r"(?m)^source: (\S+) (\d+) ([0-9a-f]{128})$", record.group(1))
            if record
            else None
        )
        if not source:
            raise ValueError(f"No matching source metadata for {package} {version}.")
        path, size, checksum = source.groups()
        if (
            not path.startswith(("src/release/", "x86_64/release/"))
            or ".." in Path(path).parts
            or int(size) > 100_000_000
        ):
            raise ValueError("Unexpected Cygwin source location or size.")
        data, source_url = download_cygwin(path, int(size))
        if len(data) != int(size) or hashlib.sha512(data).hexdigest() != checksum:
            raise ValueError("Cygwin source checksum/size mismatch.")
        (notices / Path(path).name).write_bytes(data)
        sources.append(
            {
                "package": package,
                "version": version,
                "url": source_url,
                "sha512": checksum,
            }
        )
    (notices / "cygwin-source.json").write_text(
        json.dumps(sources, indent=2) + "\n", encoding="utf-8"
    )
    for folder in (
        cygwin.parent / "usr/share/doc/Cygwin",
        cygwin.parent / "usr/share/doc/gcc",
        cygwin.parent / "usr/share/doc/libiconv",
        cygwin.parent / "usr/share/doc/gettext",
    ):
        for original in folder.glob("*"):
            if original.is_file() and (
                original.name.startswith("COPYING") or original.name == "CYGWIN_LICENSE"
            ):
                shutil.copy2(original, notices / (folder.name + "-" + original.name))


def loader_revision(source, windows=False):
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    expected = WINDOWS_LOADER_COMMIT if windows else LOADER_COMMIT
    if revision != expected:
        raise ValueError(
            f"Expected {LOADER_REPOSITORY} commit {expected}, got {revision}"
        )
    changes = subprocess.check_output(
        ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"],
        text=True,
    )
    if changes.strip():
        raise ValueError(
            "Loader source has tracked changes; use the pinned clean source."
        )
    return revision


def stage_loader(prefix, source, stage, windows):
    revision = loader_revision(source, windows=windows)
    name = "openFPGALoader.exe" if windows else "openFPGALoader"
    loader = prefix / "bin" / name
    if not loader.is_file():
        raise ValueError(f"Missing loader: {loader}")
    relative = "runtime/ucrt64" if windows else "runtime/linux"
    share = stage / relative / "share/openFPGALoader"
    share.mkdir(parents=True)
    bridge = prefix / "share/openFPGALoader" / BRIDGE
    data = (
        bridge.read_bytes()
        if bridge.is_file()
        else gzip.decompress(Path(str(bridge) + ".gz").read_bytes())
    )
    (share / BRIDGE).write_bytes(data)
    notices = stage / "THIRD-PARTY"
    notices.mkdir()
    shutil.copy2(source / "LICENSE", notices / "openFPGALoader-LICENSE")
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "archive",
            "--format=tar.gz",
            "-o",
            str(notices / "openFPGALoader-source.tar.gz"),
            revision,
        ],
        check=True,
    )
    (notices / "openFPGALoader.json").write_text(
        json.dumps(
            {
                "repository": LOADER_REPOSITORY,
                "commit": revision,
                "binary_sha256": hashlib.sha256(loader.read_bytes()).hexdigest(),
                "transport": "ftdi-d2xx" if windows else "libftdi",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    licenses = prefix / "share/licenses"
    if licenses.is_dir():
        shutil.copytree(licenses, notices / "dependency-licenses")
    return loader, relative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prefix",
        type=Path,
        required=True,
        help="Installed pinned loader prefix (bin and share)",
    )
    parser.add_argument(
        "--loader-source",
        type=Path,
        required=True,
        help="Clean pinned nobukoba/openFPGALoader checkout used for this build",
    )
    parser.add_argument(
        "--cygwin",
        type=Path,
        help="Cygwin bin directory with cygpath, cygcheck and runtime DLLs",
    )
    parser.add_argument(
        "--network-bin",
        type=Path,
        help="Windows directory containing four Cygwin-built SiTCP EXEs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/desktop"),
        help="New output directory (default: dist/desktop)",
    )
    args = parser.parse_args()
    windows = sys.platform == "win32"
    if sys.platform not in ("win32", "linux"):
        parser.error(
            "Run natively on Windows or Linux; use build-macos-app.py on macOS."
        )
    if (
        platform.machine().lower() not in ("amd64", "x86_64")
        or struct.calcsize("P") != 8
    ):
        parser.error("This builder currently targets x64/x86_64 only.")
    if windows and not args.cygwin:
        parser.error("--cygwin is required for Windows MCS operations.")
    if windows and not args.network_bin:
        parser.error("--network-bin is required for Windows SiTCP tools.")
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Use a new output directory: {output}")
    root = Path(__file__).resolve().parent
    stage = output / "staging"
    stage.mkdir(parents=True)
    loader, relative = stage_loader(
        args.prefix.resolve(), args.loader_source.resolve(), stage, windows
    )
    binaries = [(loader, relative + "/bin")]
    if windows:
        stage_cygwin(args.cygwin, stage / "THIRD-PARTY")
        binaries += [
            (path, relative + "/bin")
            for path in sorted((args.prefix / "bin").glob("*.dll"))
        ]
        for name in ("cygpath.exe", "cygwin1.dll"):
            original = args.cygwin / name
            if not original.is_file():
                parser.error(f"Missing dependency: {original}")
            binaries.append((original, "runtime/msys/bin"))
        for name in (
            "mpc-mpcx-ip-writer",
            "mpc-mpcx-ip-reader",
            "sitcp-sitcpxg-ip-writer",
            "sitcp-sitcpxg-ip-reader",
        ):
            tool = args.network_bin / (name + ".exe")
            if not tool.is_file():
                parser.error(f"Missing network utility: {tool}")
            helper_environment = os.environ.copy()
            helper_environment["PATH"] = (
                str(args.cygwin.resolve())
                + os.pathsep
                + helper_environment.get("PATH", "")
            )
            subprocess.run(
                [str(tool.resolve()), "--help"],
                check=True,
                timeout=30,
                env=helper_environment,
            )
            binaries.append((tool.resolve(), "runtime/network/bin"))
        for name in ("cygwin1.dll", "cygiconv-2.dll", "cygintl-8.dll"):
            binaries.append((args.cygwin / name, "runtime/network/bin"))
        shutil.copytree(
            root / "vendor/sitcp-utility", stage / "THIRD-PARTY/sitcp-utility"
        )
    else:
        spec = importlib.util.spec_from_file_location(
            "network_builder", root / "build-network-tools.py"
        )
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        network_bin = builder.build(root, stage / "runtime/network/bin")
        binaries += [(path, "runtime/network/bin") for path in network_bin.iterdir()]
        shutil.copytree(
            root / "vendor/sitcp-utility", stage / "THIRD-PARTY/sitcp-utility"
        )
    import certifi

    shutil.copy2(certifi.where(), stage / "runtime/cacert.pem")
    for distribution_name in ("certifi", "pyinstaller"):
        distribution = importlib.metadata.distribution(distribution_name)
        for entry in distribution.files or []:
            if "LICENSE" in str(entry).upper() or "COPYING" in str(entry).upper():
                original = Path(distribution.locate_file(entry))
                if original.is_file():
                    shutil.copy2(
                        original,
                        stage
                        / "THIRD-PARTY"
                        / (distribution_name + "-" + original.name),
                    )
    for original in (
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
    ):
        if original.is_file():
            shutil.copy2(original, stage / "THIRD-PARTY" / ("Python-" + original.name))
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        NAME,
        "--distpath",
        str(output / "app"),
        "--workpath",
        str(output / "work"),
        "--specpath",
        str(output),
        "--add-data",
        f"{stage / 'runtime'}{os.pathsep}runtime",
        "--add-data",
        f"{stage / 'THIRD-PARTY'}{os.pathsep}THIRD-PARTY",
        "--add-data",
        f"{root / 'amaneq-firmware-programer.py'}{os.pathsep}.",
    ]
    for binary, destination in binaries:
        command += ["--add-binary", f"{binary.resolve()}{os.pathsep}{destination}"]
    names = set()
    for node in ast.walk(
        ast.parse((root / "amaneq-firmware-programer.py").read_text(encoding="utf-8"))
    ):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    for name in sorted(names):
        command += ["--hidden-import", name]
    command.append(str(root / "amaneq-firmware-app.py"))
    subprocess.run(command, check=True)
    folder = output / "app" / NAME
    executable = folder / (NAME + (".exe" if windows else ""))
    for name in (
        "README.md",
        "README.ja.md",
        "FOR_DEVELOPERS.md",
        "FOR_DEVELOPERS.ja.md",
    ):
        shutil.copy2(root / name, folder / name)
    # No firmware acquisition, device writes, driver changes or host-IP changes.
    environment = os.environ.copy()
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "TCL_LIBRARY",
        "TK_LIBRARY",
        "LD_LIBRARY_PATH",
    ):
        environment.pop(name, None)
    if windows:
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        environment["PATH"] = (
            str(system_root / "System32") + os.pathsep + str(system_root)
        )
    else:
        environment["PATH"] = "/usr/bin:/bin"
    subprocess.run(
        [str(executable), "--smoke-test"], check=True, timeout=120, env=environment
    )
    subprocess.run(
        [str(executable), "--firmware-cli", "--help"],
        check=True,
        timeout=30,
        env=environment,
    )
    if not windows:
        environment["LD_LIBRARY_PATH"] = str(folder / "_internal")
    bundled_loader = folder / "_internal" / relative / "bin" / loader.name
    subprocess.run(
        [str(bundled_loader), "--list-cables"], check=True, timeout=30, env=environment
    )
    for name in (
        "mpc-mpcx-ip-writer",
        "mpc-mpcx-ip-reader",
        "sitcp-sitcpxg-ip-writer",
        "sitcp-sitcpxg-ip-reader",
    ):
        tool = (
            folder
            / "_internal/runtime/network/bin"
            / (name + (".exe" if windows else ""))
        )
        subprocess.run([str(tool), "--help"], check=True, timeout=30, env=environment)
    archive = Path(
        shutil.make_archive(
            str(output / (NAME + ("-windows-x64" if windows else "-linux-x86_64"))),
            "zip" if windows else "gztar",
            folder.parent,
            folder.name,
        )
    )
    Path(str(archive) + ".sha256").write_text(
        hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n",
        encoding="utf-8",
    )
    print(archive)


if __name__ == "__main__":
    main()
