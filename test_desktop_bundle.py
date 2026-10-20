"""Offline checks for native bundle resources and pinned loader provenance."""

import gzip
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import network_operations


def load(filename):
    spec = importlib.util.spec_from_file_location(
        filename, Path(__file__).parent / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load("build-desktop-app.py")
app = load("amaneq-firmware-app.py")


class BundleTests(unittest.TestCase):
    def test_cygwin_source_matches_installed_version_and_checksum(self):
        data = b"synthetic source archive"
        for valid in (True, False):
            checksum = hashlib.sha512(data).hexdigest() if valid else "0" * 128
            metadata = "".join(
                f"@ {name}\nversion: 1.2.3-1\nsource: src/release/cygwin/source.tar.xz {len(data)} {checksum}\n"
                for name in ("cygwin", "libiconv2", "libintl8")
            ).encode()
            with tempfile.TemporaryDirectory() as directory:
                notices = Path(directory)
                with (
                    patch.object(
                        builder.subprocess,
                        "check_output",
                        return_value="cygwin 1.2.3-1 OK\nlibiconv2 1.2.3-1 OK\nlibintl8 1.2.3-1 OK\n",
                    ),
                    patch.object(
                        builder.urllib.request,
                        "urlopen",
                        side_effect=[
                            io.BytesIO(metadata),
                            io.BytesIO(data),
                            io.BytesIO(data),
                            io.BytesIO(data),
                        ],
                    ),
                ):
                    if valid:
                        builder.stage_cygwin(notices / "bin", notices)
                        self.assertEqual((notices / "source.tar.xz").read_bytes(), data)
                    else:
                        with self.assertRaisesRegex(
                            ValueError, "checksum/size mismatch"
                        ):
                            builder.stage_cygwin(notices / "bin", notices)
                        self.assertFalse((notices / "source.tar.xz").exists())

    def test_linux_bundle_loader_wins_over_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            loader = root / "runtime/linux/bin/openFPGALoader"
            loader.parent.mkdir(parents=True)
            loader.touch()
            with (
                patch.object(app, "ROOT", root),
                patch.object(app.sys, "platform", "linux"),
                patch.object(app.os, "name", "posix"),
            ):
                self.assertEqual(app.default_loader(), str(loader))

    def test_windows_network_utility_resolves_exe(self):
        with tempfile.TemporaryDirectory() as directory:
            tool = Path(directory) / "runtime/network/bin/mpc-mpcx-ip-reader.exe"
            tool.parent.mkdir(parents=True)
            tool.touch()
            with patch.object(network_operations.sys, "platform", "win32"):
                self.assertEqual(
                    network_operations.utility_path(directory, "mpc-mpcx-ip-reader"),
                    str(tool),
                )

    def test_windows_requires_d2xx_branch_commit(self):
        with patch.object(
            builder.subprocess,
            "check_output",
            side_effect=[builder.WINDOWS_LOADER_COMMIT + "\n", ""],
        ):
            self.assertEqual(
                builder.loader_revision(Path("source"), windows=True),
                builder.WINDOWS_LOADER_COMMIT,
            )
        with patch.object(
            builder.subprocess,
            "check_output",
            return_value=builder.LOADER_COMMIT + "\n",
        ):
            with self.assertRaises(ValueError):
                builder.loader_revision(Path("source"), windows=True)

    def test_reject_different_or_modified_loader_source(self):
        for output in (
            ("0" * 40 + "\n",),
            (builder.LOADER_COMMIT + "\n", " M src/main.cpp\n"),
        ):
            with patch.object(builder.subprocess, "check_output", side_effect=output):
                with self.assertRaises(ValueError):
                    builder.loader_revision(Path("source"))

    def test_bridge_is_uncompressed_and_matching_source_is_archived(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prefix = root / "prefix"
            (prefix / "bin").mkdir(parents=True)
            (prefix / "bin/openFPGALoader").write_bytes(b"synthetic loader")
            share = prefix / "share/openFPGALoader"
            share.mkdir(parents=True)
            (share / (builder.BRIDGE + ".gz")).write_bytes(
                gzip.compress(b"synthetic bridge")
            )
            source = root / "source"
            source.mkdir()
            (source / "LICENSE").write_text("Synthetic license", encoding="utf-8")
            with (
                patch.object(
                    builder, "loader_revision", return_value=builder.LOADER_COMMIT
                ),
                patch.object(builder.subprocess, "run") as run,
            ):
                builder.stage_loader(prefix, source, root / "stage", False)
            self.assertEqual(
                (
                    root / "stage/runtime/linux/share/openFPGALoader" / builder.BRIDGE
                ).read_bytes(),
                b"synthetic bridge",
            )
            self.assertIn(builder.LOADER_COMMIT, run.call_args.args[0])
            self.assertTrue((root / "stage/THIRD-PARTY/openFPGALoader.json").is_file())


if __name__ == "__main__":
    unittest.main()
