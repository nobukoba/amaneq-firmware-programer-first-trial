#!/usr/bin/env python3
"""Build a self-contained macOS application on a native Intel or Apple Silicon Mac."""

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
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request

NAME = "amaneq-firmware-programer"


def capture(*command):
    return subprocess.check_output(command, text=True).strip()


def hidden_imports(path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return sorted(names)


def fetch_source(info, destination):
    source = info["urls"]["stable"]
    url, expected = source["url"], source["checksum"]
    if not url.startswith("https://") or not re.fullmatch(
        r"[0-9a-f]{64}", expected or ""
    ):
        raise RuntimeError(f"No verifiable HTTPS source archive for {info['name']}")
    request = urllib.request.Request(
        url, headers={"User-Agent": "AMANEQ-desktop-builder"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f"Source checksum mismatch for {info['name']}")
    destination.write_bytes(data)
    # Copy notices from the verified source without extracting arbitrary paths.
    with tarfile.open(destination) as archive:
        for member in archive.getmembers():
            leaf = Path(member.name).name
            if (
                member.isfile()
                and len(Path(member.name).parts) <= 2
                and re.match(r"^(COPYING|LICENSE|NOTICE)", leaf, re.I)
            ):
                handle = archive.extractfile(member)
                (destination.parent / f"{info['name']}-{leaf}").write_bytes(
                    handle.read()
                )


def audit_dependencies(app):
    visited = set()
    for candidate in app.rglob("*"):
        if not candidate.is_file():
            continue
        path = candidate.resolve()
        if path in visited:
            continue
        visited.add(path)
        with path.open("rb") as handle:
            magic = handle.read(4)
        if magic not in (
            b"\xcf\xfa\xed\xfe",
            b"\xce\xfa\xed\xfe",
            b"\xca\xfe\xba\xbe",
            b"\xca\xfe\xba\xbf",
        ):
            continue
        output = capture("otool", "-L", str(path))
        for line in output.splitlines()[1:]:
            dependency = line.strip().split(" (", 1)[0]
            if dependency.startswith("/") and not dependency.startswith(
                ("/usr/lib/", "/System/Library/")
            ):
                raise RuntimeError(
                    f"External runtime dependency in {path.name}: {dependency}"
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/macos"),
        help="New build directory (default: dist/macos)",
    )
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Build on macOS; Windows/Linux cannot produce this .app.")
    import certifi

    architecture = platform.machine()
    if architecture not in ("arm64", "x86_64"):
        parser.error(f"Unsupported architecture: {architecture}")
    root = Path(__file__).resolve().parent
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Use a new output directory: {output}")
    output.mkdir(parents=True)
    prefix = Path(capture("brew", "--prefix", "openfpgaloader")).resolve()
    loader = prefix / "bin/openFPGALoader"
    stage = output / "staging"
    share = stage / "runtime/macos/share/openFPGALoader"
    share.mkdir(parents=True)
    # Ship an uncompressed bridge; no app-bundle writes are needed at runtime.
    bridge_name = "spiOverJtag_xc7k160tffg676.bit"
    bridge = prefix / "share/openFPGALoader" / bridge_name
    bridge_bytes = (
        bridge.read_bytes()
        if bridge.exists()
        else gzip.decompress(Path(str(bridge) + ".gz").read_bytes())
    )
    (share / bridge_name).write_bytes(bridge_bytes)
    notices = stage / "THIRD-PARTY"
    notices.mkdir()
    information = json.loads(
        capture("brew", "info", "--json=v2", "openfpgaloader", "libftdi", "libusb")
    )
    (notices / "homebrew-formulae.json").write_text(
        json.dumps(information, indent=2), encoding="utf-8"
    )
    for info in information["formulae"]:
        installed = info.get("installed", [])
        stable = info["versions"]["stable"]
        expected_version = stable + (
            f"_{info['revision']}" if info.get("revision") else ""
        )
        if not installed or not any(
            item["version"] == expected_version for item in installed
        ):
            raise RuntimeError(f"Installed/source version mismatch for {info['name']}")
        fetch_source(info, notices / f"{info['name']}-source.tar")
        formula_prefix = Path(capture("brew", "--prefix", info["name"])).resolve()
        for recipe in (formula_prefix / ".brew").glob("*.rb"):
            shutil.copy2(recipe, notices / recipe.name)
    certificate_distribution = importlib.metadata.distribution("certifi")
    (notices / "certifi-version.txt").write_text(
        certificate_distribution.version + "\n", encoding="utf-8"
    )
    for entry in certificate_distribution.files or []:
        if "LICENSE" in str(entry).upper():
            original = Path(certificate_distribution.locate_file(entry))
            if original.is_file():
                shutil.copy2(original, notices / ("certifi-" + original.name))
    distribution = importlib.metadata.distribution("pyinstaller")
    for entry in distribution.files or []:
        if "/licenses/" in str(entry).replace("\\", "/"):
            original = Path(distribution.locate_file(entry))
            if original.is_file():
                shutil.copy2(original, notices / ("PyInstaller-" + original.name))
    for path in [
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "Resources/English.lproj/License.rtf",
    ]:
        if path.is_file():
            shutil.copy2(path, notices / ("Python-" + path.name))
    spec = importlib.util.spec_from_file_location(
        "network_builder", root / "build-network-tools.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    network_bin = builder.build(root, stage / "runtime/network/bin")
    shutil.copytree(
        root / "vendor/sitcp-utility", notices / "sitcp-utility", dirs_exist_ok=True
    )
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        NAME,
        "--osx-bundle-identifier",
        "org.nobukoba.amaneq-firmware-programer",
        "--target-architecture",
        architecture,
        "--distpath",
        str(output / "app"),
        "--workpath",
        str(output / "work"),
        "--specpath",
        str(output),
        "--add-binary",
        f"{loader}:runtime/macos/bin",
        "--add-data",
        f"{stage / 'runtime/macos/share'}:runtime/macos/share",
        "--add-data",
        f"{root / 'amaneq-firmware-programer.py'}:.",
        "--add-data",
        f"{notices}:THIRD-PARTY",
    ]
    for tool in network_bin.iterdir():
        command += ["--add-binary", f"{tool}:runtime/network/bin"]
    command += ["--add-data", f"{certifi.where()}:runtime"]
    for name in hidden_imports(root / "amaneq-firmware-programer.py"):
        command += ["--hidden-import", name]
    command.append(str(root / "amaneq-firmware-app.py"))
    subprocess.run(command, check=True)
    app = output / "app" / (NAME + ".app")
    info_path = app / "Contents/Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    info.update(
        {"LSMinimumSystemVersion": "15.0", "CFBundleShortVersionString": "0.14.4"}
    )
    info_path.write_bytes(plistlib.dumps(info))
    for name in (
        "README.md",
        "README.ja.md",
        "FOR_DEVELOPERS.md",
        "FOR_DEVELOPERS.ja.md",
    ):
        shutil.copy2(root / name, app / "Contents/Resources" / name)
    audit_dependencies(app)
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True
    )
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    executable = app / "Contents/MacOS" / NAME
    environment = {**os.environ, "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
    subprocess.run(
        [str(executable), "--smoke-test"], check=True, env=environment, timeout=90
    )
    bundled_loader = next((app / "Contents/Frameworks").rglob("openFPGALoader"))
    subprocess.run(
        [str(bundled_loader), "--list-cables"], check=True, env=environment, timeout=30
    )
    subprocess.run(
        [str(executable), "--firmware-cli", "scan", "--loader", str(bundled_loader)],
        check=True,
        env=environment,
        timeout=45,
    )
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    archive = output / f"{NAME}-macos-{architecture}.zip"
    subprocess.run(
        [
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(app),
            str(archive),
        ],
        check=True,
    )
    (output / (archive.name + ".sha256")).write_text(
        hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n",
        encoding="utf-8",
    )
    print(archive)


if __name__ == "__main__":
    main()
