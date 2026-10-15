#!/usr/bin/env python3
"""Build a local Windows x64 desktop bundle from explicit dependency paths."""

import argparse
import ast
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ucrt",
        type=Path,
        required=True,
        help="openFPGALoader UCRT64 prefix, including bin and share",
    )
    parser.add_argument(
        "--libwdi",
        type=Path,
        required=True,
        help="Official-source-built x64 libwdi DLL",
    )
    parser.add_argument(
        "--libwdi-source",
        type=Path,
        required=True,
        help="Matching libwdi source checkout including COPYING",
    )
    parser.add_argument(
        "--cygwin",
        type=Path,
        required=True,
        help="Directory containing cygpath.exe and cygwin1.dll",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist"),
        help="Build/output directory (default: dist)",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    for path in [
        args.ucrt / "bin/openFPGALoader.exe",
        args.libwdi,
        args.libwdi_source / "COPYING",
        args.cygwin / "cygpath.exe",
        args.cygwin / "cygwin1.dll",
    ]:
        if not path.is_file():
            parser.error(f"Missing dependency: {path}")
    stage = args.output.resolve() / "staging"
    if stage.exists():
        parser.error(f"Use a new output directory; staging already exists: {stage}")
    runtime = stage / "runtime"
    runtime.mkdir(parents=True)
    shutil.copytree(args.ucrt, runtime / "ucrt64")
    shutil.copy2(args.libwdi, runtime / "libwdi.dll")
    (runtime / "msys/bin").mkdir(parents=True)
    for name in ["cygpath.exe", "cygwin1.dll"]:
        shutil.copy2(args.cygwin / name, runtime / "msys/bin" / name)
    shutil.copy2(args.libwdi_source / "COPYING", runtime / "LIBWDI-COPYING.txt")
    subprocess.run(
        [
            "git",
            "-C",
            str(args.libwdi_source.resolve()),
            "archive",
            "--format=tar.gz",
            "-o",
            str(runtime / "libwdi-matching-source.tar.gz"),
            "HEAD",
        ],
        check=True,
    )
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "amaneq-firmware-programer",
        "--distpath",
        str(args.output.resolve() / "app"),
        "--workpath",
        str(args.output.resolve() / "work"),
        "--specpath",
        str(args.output.resolve()),
        "--add-data",
        f"{runtime};runtime",
        "--add-data",
        f'{root / "amaneq-firmware-programer.py"};.',
    ]
    # The CLI is loaded from its unchanged source file; include its static imports.
    tree = ast.parse(
        (root / "amaneq-firmware-programer.py").read_text(encoding="utf-8")
    )
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    for name in sorted(names):
        command += ["--hidden-import", name]
    command += [str(root / "amaneq-firmware-app.py")]
    subprocess.run(command, check=True)
    folder = args.output.resolve() / "app/amaneq-firmware-programer"
    for name in [
        "README.md",
        "README.ja.md",
        "FOR_DEVELOPERS.md",
        "FOR_DEVELOPERS.ja.md",
    ]:
        shutil.copy2(root / name, folder / name)
    shutil.make_archive(
        str(args.output.resolve() / "amaneq-firmware-programer-windows-x64"),
        "zip",
        folder.parent,
        folder.name,
    )
    print(folder / "amaneq-firmware-programer.exe")


if __name__ == "__main__":
    main()
