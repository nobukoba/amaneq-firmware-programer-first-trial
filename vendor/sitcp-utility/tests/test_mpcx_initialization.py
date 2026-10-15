"""Cleared EEPROM initialization and write-failure tests; synthetic data only."""
import pathlib
import tempfile
import unittest

from test_register_report import Device

PAYLOAD = bytes([0x2C] * 7 + list(range(9)) + [0x02, 0x01, 0x02, 0x03, 0x04, 0x05])


def write_mpcx(device, *options):
    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / 'synthetic.mpcx'
        path.write_bytes(PAYLOAD)
        return device.run('mpc-mpcx-ip-writer', '127.0.0.1', str(path), *options)


def region(device, base, length):
    return bytes(device.memory.get(base + i, 0) for i in range(length))


def expected_image(device):
    image = bytearray(region(device, 0xFFFFFF00, 80))
    image[:16] = PAYLOAD[:16]
    image[18:24] = PAYLOAD[16:]
    return bytes(image)


class InitializationTests(unittest.TestCase):
    def test_clear_then_write_restores_runtime(self):
        device = Device()
        try:
            result = device.run('mpc-mpcx-ip-command', 'clear', '127.0.0.1', '--yes-really-clear')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(region(device, 0xFFFFFC00, 128), bytes([255] * 128))
            runtime = region(device, 0xFFFFFF00, 80)
            device.requests.clear()
            expected = expected_image(device)
            result = write_mpcx(device)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.endswith('\n\nSuccess! All operations completed and verified.\n\n'))
            self.assertEqual(region(device, 0xFFFFFC00, 80), expected)
            self.assertEqual(region(device, 0xFFFFFC40, 2), b'\x27\x10')
            self.assertEqual(region(device, 0xFFFFFC50, 48), bytes([255] * 48))
            self.assertEqual(region(device, 0xFFFFFF00, 80), runtime)
            writes = [req for req in device.requests if req[0] == 0x80]
            self.assertEqual(writes, [(0x80, 0xFFFFFCFF, 1)] +
                             [(0x80, 0xFFFFFC00, 80)] +
                             [(0x80, 0xFFFFFCFF, 1)])
            self.assertEqual(device.memory[0xFFFFFCFF], 255)
            first_write = next(i for i, req in enumerate(device.requests) if req[0] == 0x80)
            self.assertTrue(any(req[1] == 0xFFFFFF48 for req in device.requests[:first_write]))
        finally:
            device.close()

    def test_initialized_eeprom_is_preserved(self):
        device = Device(rate=10000)
        try:
            before = region(device, 0xFFFFFC00, 80)
            result = write_mpcx(device)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('existing EEPROM settings preserved', result.stdout)
            self.assertTrue(result.stdout.endswith('\n\nSuccess! All operations completed and verified.\n\n'))
            self.assertEqual(region(device, 0xFFFFFC10, 2), before[16:18])
            self.assertEqual(region(device, 0xFFFFFC18, 56), before[24:])
            self.assertEqual(region(device, 0xFFFFFC40, 2), b'\x03\xe8')
            writes = [req for req in device.requests if req[0] == 0x80 and req[1] != 0xFFFFFCFF]
            self.assertEqual(writes, [(0x80, 0xFFFFFC00, 24)])
        finally:
            device.close()

    def test_control_bit_not_whole_image_triggers_initialization(self):
        device = Device()
        try:
            device.memory[0xFFFFFC10] = 0x90
            expected = expected_image(device)
            result = write_mpcx(device)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(region(device, 0xFFFFFC00, 80), expected)
        finally:
            device.close()

    def test_incomplete_runtime_never_programs_placeholders(self):
        for fault in ('bus', 'rate', 'short'):
            device = Device(fault=fault)
            try:
                device.put(0xFFFFFC00, bytes([255] * 80))
                result = write_mpcx(device)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(req[0] == 0x80 for req in device.requests))
                self.assertEqual(region(device, 0xFFFFFC00, 80), bytes([255] * 80))
                if fault != 'short':
                    self.assertIn('No EEPROM writes performed', result.stderr)
            finally:
                device.close()

    def test_runtime_reset_bit_refused(self):
        device = Device()
        try:
            device.memory[0xFFFFFC10] = 255
            device.memory[0xFFFFFF10] = 128
            result = write_mpcx(device)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('RESET bit', result.stderr)
            self.assertFalse(any(req[0] == 0x80 for req in device.requests))
        finally:
            device.close()

    def test_write_failures_restore_protection_without_retry(self):
        for fault in ('write_bus', 'write_timeout', 'verify_mismatch', 'enable_timeout'):
            device = Device(fault=fault)
            try:
                device.put(0xFFFFFC00, bytes([255] * 80))
                result = write_mpcx(device)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('Success!', result.stdout)
                self.assertEqual(device.memory[0xFFFFFCFF], 255)
                writes = [req for req in device.requests if req[0] == 0x80]
                self.assertEqual(writes[-1], (0x80, 0xFFFFFCFF, 1))
                self.assertEqual(writes.count((0x80, 0xFFFFFCFF, 1)), 2)
                self.assertEqual(writes.count((0x80, 0xFFFFFC00, 80)),
                                 0 if fault == 'enable_timeout' else 1)
            finally:
                device.close()

    def test_explicit_ip_overrides_follow_initialization(self):
        device = Device()
        try:
            device.put(0xFFFFFC00, bytes([255] * 80))
            result = write_mpcx(device, '--set-eeprom-ip', '192.0.2.42',
                               '--set-current-ip', '127.0.0.1')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(region(device, 0xFFFFFC18, 4), bytes([192, 0, 2, 42]))
            writes = [req for req in device.requests if req[0] == 0x80]
            self.assertLess(writes.index((0x80, 0xFFFFFC00, 80)),
                            writes.index((0x80, 0xFFFFFC18, 40)))
            self.assertLess(writes.index((0x80, 0xFFFFFC18, 40)),
                            writes.index((0x80, 0xFFFFFF18, 40)))
        finally:
            device.close()

    def test_plan_matches_writer_image_without_writes(self):
        for initialized in (False, True):
            device = Device()
            try:
                if not initialized:
                    device.put(0xFFFFFC00, bytes([255] * 80))
                with tempfile.TemporaryDirectory() as directory:
                    path = pathlib.Path(directory) / 'synthetic.mpcx'
                    path.write_bytes(PAYLOAD)
                    result = device.run('mpc-mpcx-ip-command', 'mpcx-plan',
                                        '127.0.0.1', str(path))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(any(req[0] == 0x80 for req in device.requests))
                image_line = next(line for line in result.stdout.splitlines()
                                  if line.startswith('EEPROM record'))
                planned = bytes.fromhex(image_line.split(':', 1)[1])
                self.assertEqual(len(planned), 24 if initialized else 80)
                result = write_mpcx(device)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(region(device, 0xFFFFFC00, len(planned)), planned)
            finally:
                device.close()

    def test_mismatched_device_never_writes(self):
        device = Device(xg=False)
        try:
            device.put(0xFFFFFC00, bytes([255] * 80))
            result = write_mpcx(device)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertFalse(any(req[0] == 0x80 for req in device.requests))
        finally:
            device.close()


if __name__ == '__main__':
    unittest.main()
