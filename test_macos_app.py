import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parent / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


app = load("desktop_app", "amaneq-firmware-app.py")
builder = load("macos_builder", "build-macos-app.py")


class MacBundleTests(unittest.TestCase):
    def test_macos_data_is_outside_app(self):
        with (
            patch.object(app.sys, "platform", "darwin"),
            patch.object(app.Path, "home", return_value=Path("/Users/example")),
        ):
            self.assertEqual(
                app.app_data_directory().as_posix(),
                "/Users/example/Library/Application Support/AMANEQ",
            )

    def test_bundled_loader_preferred_without_homebrew(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(app, "ROOT", Path(tmp)),
            patch.object(app.sys, "platform", "darwin"),
        ):
            loader = Path(tmp) / "runtime/macos/bin/openFPGALoader"
            loader.parent.mkdir(parents=True)
            loader.write_bytes(b"fixture")
            self.assertEqual(Path(app.default_loader()), loader)

    def test_dependency_audit_rejects_homebrew(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "binary").write_bytes(b"\xcf\xfa\xed\xfe")
            with patch.object(
                builder,
                "capture",
                return_value="binary:\n /opt/homebrew/opt/libusb/lib/libusb.dylib (compatibility version 1)",
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "External runtime dependency"
                ):
                    builder.audit_dependencies(folder)
            with patch.object(
                builder,
                "capture",
                return_value="binary:\n @rpath/libusb.dylib (compatibility version 1)\n /usr/lib/libSystem.B.dylib (compatibility version 1)",
            ):
                builder.audit_dependencies(folder)

    def test_source_checksum_failure_never_saves_archive(self):
        import io

        info = {
            "name": "fixture",
            "urls": {
                "stable": {
                    "url": "https://example.invalid/source.tar",
                    "checksum": "0" * 64,
                }
            },
        }
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(
                builder.urllib.request, "urlopen", return_value=io.BytesIO(b"corrupt")
            ),
        ):
            destination = Path(tmp) / "source.tar"
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                builder.fetch_source(info, destination)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
