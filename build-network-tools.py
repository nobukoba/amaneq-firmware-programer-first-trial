#!/usr/bin/env python3
"""Build the pinned SiTCP utilities for native Linux, WSL or macOS."""

import argparse
from pathlib import Path
import shutil
import subprocess

NAMES = ("mpc-mpcx-ip-writer", "mpc-mpcx-ip-reader", "sitcp-sitcpxg-ip-writer")


def build(root, output, compiler="c++"):
    source = root / "vendor/sitcp-utility/src"
    output.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        target = output / name
        subprocess.run(
            [
                compiler,
                "-std=c++11",
                "-O2",
                "-Wall",
                "-Wextra",
                str(source / (name + ".cpp")),
                "-o",
                str(target),
            ],
            check=True,
        )
        subprocess.run([str(target), "--help"], check=True, capture_output=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="c++", help="C++ compiler (default: c++)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if not shutil.which(args.compiler):
        parser.error(
            "A native C++ compiler is required (Xcode command-line tools or g++)."
        )
    build(root, root / "runtime/network/bin", args.compiler)


if __name__ == "__main__":
    main()
