import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import windows_usb as usb

DEVICE = {
    "instance": r"USB\VID_0403&PID_6014\TEST",
    "serial": "TEST",
    "service": "FTDIBUS",
    "inf": "oem42.inf",
}


class DriverTests(unittest.TestCase):
    def test_changes_require_one_explicit_device(self):
        for serial, found in [
            (None, [DEVICE]),
            ("OTHER", [DEVICE]),
            ("TEST", []),
            ("TEST", [DEVICE, DEVICE]),
        ]:
            with self.assertRaises(usb.DriverError):
                usb.select(serial, found)
        self.assertEqual(usb.select("TEST", [DEVICE]), DEVICE)

    def test_backup_hash_and_device_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            original = base / "original"
            original.mkdir()
            inf = original / "ftdibus.inf"
            inf.write_bytes(b"synthetic signed-driver fixture")
            manifest = {
                "schema": 1,
                "device": DEVICE,
                "inf": "ftdibus.inf",
                "sha256": usb.file_hashes(original),
            }
            self.assertEqual(usb.validate_backup(DEVICE, base, manifest), inf.resolve())
            other = {**DEVICE, "instance": "OTHER"}
            with self.assertRaises(usb.DriverError):
                usb.validate_backup(other, base, manifest)
            traversal = {**manifest, "inf": "../ftdibus.inf"}
            with self.assertRaises(usb.DriverError):
                usb.validate_backup(DEVICE, base, traversal)
            inf.write_bytes(b"changed")
            with self.assertRaises(usb.DriverError):
                usb.validate_backup(DEVICE, base, manifest)

    def test_backup_before_any_replacement_and_never_overwritten(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(usb, "state_root", return_value=Path(tmp)),
        ):

            def export(command):
                self.assertEqual(
                    command[:3], ["pnputil.exe", "/export-driver", "oem42.inf"]
                )
                (Path(command[3]) / "ftdibus.inf").write_bytes(b"synthetic INF")
                return ""

            with patch.object(usb, "run", side_effect=export) as call:
                base, first = usb.checked_backup(DEVICE)
                second = usb.checked_backup(DEVICE)[1]
            self.assertEqual(call.call_count, 1)
            self.assertEqual(first, second)
            self.assertTrue((base / "original.json").is_file())

    def test_first_backup_rejects_winusb_and_unexpected_inf(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(usb, "state_root", return_value=Path(tmp)),
            patch.object(usb, "run") as call,
        ):
            for changed in [{"service": "WinUSB"}, {"inf": "unexpected.inf"}]:
                with self.assertRaises(usb.DriverError):
                    usb.checked_backup({**DEVICE, **changed})
            call.assert_not_called()

    def test_dll_structure_abi(self):
        if usb.c.sizeof(usb.c.c_void_p) == 8:
            self.assertEqual(usb.c.sizeof(usb.WdiDevice), 80)
            self.assertEqual(usb.c.sizeof(usb.WdiPrepareOptions), 48)
        self.assertEqual(usb.c.sizeof(usb.WdiListOptions), 12)

    def test_failed_export_keeps_partial_files_without_manifest(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(usb, "state_root", return_value=Path(tmp)),
        ):

            def fail(command):
                (Path(command[3]) / "partial").write_bytes(b"partial")
                raise usb.DriverError("export failed")

            with (
                patch.object(usb, "run", side_effect=fail),
                self.assertRaises(usb.DriverError),
            ):
                usb.checked_backup(DEVICE)
            with (
                patch.object(usb, "run") as call,
                self.assertRaisesRegex(usb.DriverError, "Incomplete"),
            ):
                usb.checked_backup(DEVICE)
            call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
