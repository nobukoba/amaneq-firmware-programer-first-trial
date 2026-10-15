"""Protocol regression tests without contacting connected hardware."""

import tempfile
from pathlib import Path
import struct
import unittest
from unittest.mock import patch, MagicMock
import network_operations as ops


class ClockDevice:
    def __init__(self, mismatch=False):
        self.words = [0x11111110, 0x22222221]
        self.tx = 0
        self.rx = 0
        self.saved = False
        self.mismatch = mismatch
        self.addresses = []

    def write(self, address, value):
        self.addresses.append(address)
        if 0xB0000000 <= address <= 0xB0030000 and (address & 0xFFFF) == 0:
            lane = (address - 0xB0000000) >> 16
            self.tx = (self.tx & ~(255 << (8 * lane))) | value << (8 * lane)
        elif address == 0xB1000000:
            word = ops.reverse32(self.tx)
            if word == 0x1F:
                self.saved = True
            else:
                self.words[word & 15] = word ^ (0x100 if self.mismatch else 0)
        else:
            raise AssertionError(hex(address))

    def read(self, address):
        if address == 0xB2000000:
            register = (ops.reverse32(self.tx) >> 4) & 15
            self.rx = ops.reverse32(self.words[register])
            return 0
        lane = (address - 0xB0100000) >> 16
        return (self.rx >> (8 * lane)) & 255


class NetworkOperationTests(unittest.TestCase):
    def test_clock_byte_lane_spacing_and_verify_before_eeprom(self):
        for preset in ops.PRESETS:
            device = ClockDevice()
            result = ops.configure_clock(
                "192.168.10.10", preset, True, lambda host: device
            )
            self.assertTrue(device.saved)
            self.assertEqual(device.words, list(ops.PRESETS[preset]))
            self.assertIn("acknowledged", result)
            self.assertIn(0xB0030000, device.addresses)
            self.assertNotIn(0xB0000001, device.addresses)
        device = ClockDevice(mismatch=True)
        with self.assertRaisesRegex(RuntimeError, "readback mismatch"):
            ops.configure_clock(
                "192.168.10.10", next(iter(ops.PRESETS)), True, lambda host: device
            )
        self.assertFalse(device.saved)

    def test_runtime_clock_does_not_copy_to_eeprom(self):
        device = ClockDevice()
        ops.configure_clock(
            "192.168.10.16", next(iter(ops.PRESETS)), False, lambda host: device
        )
        self.assertFalse(device.saved)

    def test_presets_match_hul_register_fields(self):
        # Independent original register-field encodings from CDCE62002RegMap.hh.
        for name, divider, prescale, output0, output1 in [
            ("in_100_out_500_100", 4, 2, 1, 5),
            ("in_125_out_500_125", 5, 2, 1, 4),
            ("in_125_out_625_125", 4, 1, 1, 5),
            ("in_75_out_375_75", 4, 0, 1, 5),
            ("in_50_out_250_50", 2, 2, 2, 10),
            ("in_100_out_250_50", 4, 2, 2, 10),
        ]:
            reg0 = (
                (1 << 4)
                | (1 << 6)
                | (1 << 8)
                | (output0 << 19)
                | (output1 << 23)
                | (1 << 28)
                | (1 << 30)
            )
            reg1 = (
                0x80000001
                | ((divider - 1) << 5)
                | (prescale << 13)
                | (3 << 15)
                | (7 << 23)
                | (3 << 26)
            )
            self.assertEqual(ops.PRESETS[name], (reg0, reg1))

    def test_endpoint_and_commands_keep_read_and_write_separate(self):
        self.assertEqual(ops.endpoint("MPC", ""), "192.168.10.16")
        self.assertEqual(ops.endpoint("MPCX", ""), "192.168.10.10")
        self.assertEqual(ops.endpoint("Custom", "192.168.2.5"), "192.168.2.5")
        with patch.object(ops, "utility_path", side_effect=lambda root, name: name):
            self.assertEqual(
                ops.utility_command(".", "192.168.10.10", "Check")[-1], "--check"
            )
            command = ops.utility_command(
                ".", "192.168.10.10", "Write IP only", new_ip="192.168.10.12"
            )
            self.assertEqual(command[-1], "--eeprom")
            with self.assertRaises(ValueError):
                ops.utility_command(".", "192.168.10.10", "Write MPC/MPCX")

    def test_cirasame_images_are_isolated_from_amaneq(self):
        import argparse
        from desktop_services import load_core

        core = load_core(Path(__file__).parent, Path("unused"))
        entries = [
            {"path": "mcs/cirasame-strtdc-v2.9.mcs"},
            {"path": "mcs/amaneq-4-strlrtdc-v2.A.mcs"},
        ]
        args = argparse.Namespace(
            target="cirasame", firmware="lrtdc", format="mcs", flash="auto"
        )
        selected = core.candidates(entries, args)
        self.assertEqual([row["path"] for row in selected], [entries[0]["path"]])
        args.target = "amaneq-v4"
        self.assertEqual(
            [row["path"] for row in core.candidates(entries, args)],
            [entries[1]["path"]],
        )
        self.assertEqual(core.filename_family("cirasame-skeleton-v2.0.bit"), "skeleton")
        self.assertEqual(
            core.filename_family("cirasame-strtdc10g-v2.3.mcs"), "lrtdc-10g"
        )

    def test_license_labels_match_official_synthetic_payloads(self):
        import json

        reference = Path(__file__).parent / "vendor/sitcp-utility/tests/reference"
        with tempfile.TemporaryDirectory() as directory:
            for fixture, expected in (
                ("official_mpc_erased.json", "MPC"),
                ("official_mpcx_erased.json", "MPCX"),
            ):
                payload = bytes.fromhex(
                    json.loads((reference / fixture).read_text())["synthetic_payload"]
                )
                path = Path(directory) / "misleading-extension.bin"
                path.write_bytes(payload)
                self.assertEqual(ops.license_kind(path), expected)

    def test_ping_platform_flags_and_timeout(self):
        self.assertIn("1000", ops.ping_command("192.168.10.10", "darwin"))
        self.assertEqual(
            ops.ping_command("192.168.10.16", "linux")[-2:], ["1", "192.168.10.16"]
        )
        self.assertIn("-n", ops.ping_command("192.168.10.10", "win32"))
        with patch.object(
            ops.subprocess, "run", side_effect=ops.subprocess.TimeoutExpired("ping", 8)
        ) as run:
            success, output = ops.ping_target("192.168.10.10")
            self.assertFalse(success)
            self.assertIn("timed out", output)
            self.assertEqual(run.call_count, 1)

    def test_rbcp_rejects_bus_error_short_ack_and_timeout_without_retry(self):
        for reply in (b"", struct.pack("!BBBBI", 255, 0xC9, 1, 1, 0xB2000000) + b"\0"):
            client = MagicMock()
            client.recv.return_value = reply
            with patch.object(ops.socket, "socket") as factory:
                factory.return_value.__enter__.return_value = client
                with self.assertRaisesRegex(RuntimeError, "ACK"):
                    ops.Rbcp("192.168.10.10").read(0xB2000000)
                self.assertEqual(client.send.call_count, 1)
        with patch.object(ops.socket, "socket") as factory:
            client = factory.return_value.__enter__.return_value
            client.recv.side_effect = TimeoutError("timed out")
            with self.assertRaisesRegex(RuntimeError, "No automatic write retry"):
                ops.Rbcp("192.168.10.10").write(0xB1000000, 0)
            self.assertEqual(client.send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
