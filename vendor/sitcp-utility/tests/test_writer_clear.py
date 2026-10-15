"""Writer clear-only CLI and shared erase failure handling."""
import unittest

from test_register_report import Device


class WriterClearTests(unittest.TestCase):
    def test_clear_only_both_generations(self):
        for xg in (False, True):
            device = Device(xg=xg)
            try:
                runtime = {address: value for address, value in device.memory.items()
                           if address >= 0xFFFFFF00}
                result = device.run('mpc-mpcx-ip-writer', '127.0.0.1', '--clear')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Success!', result.stdout)
                self.assertEqual(len(result.stdout.splitlines()), 7)
                self.assertNotIn('EEPROM initialization:', result.stdout)
                self.assertIn('before:', result.stdout)
                self.assertIn('after:', result.stdout)
                self.assertEqual(bytes(device.memory[0xFFFFFC00 + i] for i in range(128)),
                                 bytes([255] * 128))
                self.assertEqual(device.memory[0xFFFFFCFF], 255)
                self.assertEqual(runtime, {address: value for address, value in device.memory.items()
                                           if address >= 0xFFFFFF00})
                writes = [request for request in device.requests if request[0] == 0x80]
                self.assertEqual(writes, [(0x80, 0xFFFFFCFF, 1)] +
                                 [(0x80, 0xFFFFFC00 + i, 16) for i in range(0, 128, 16)] +
                                 [(0x80, 0xFFFFFCFF, 1)])
                times = [when for when, request in zip(device.request_times, device.requests)
                         if request[0] == 0x80]
                for earlier, later in zip(times, times[1:]):
                    self.assertGreaterEqual(later - earlier, 0.45)
                if not xg:
                    self.assertFalse(any(address < 0xFFFFFF50 and address + length > 0xFFFFFF40
                                         for _, address, length in device.requests))
            finally:
                device.close()

    def test_conflicts_rejected_before_device_access(self):
        for args in (
            ['missing.mpcx', '--clear'],
            ['--clear', 'missing.mpcx'],
            ['--clear', '--set-eeprom-ip', '192.0.2.1'],
            ['--clear', '--set-current-ip', '192.0.2.1'],
            ['--clear-first'],
            ['--clear', '--write-chunk-size', '16'],
        ):
            device = Device()
            try:
                result = device.run('mpc-mpcx-ip-writer', '127.0.0.1', *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(device.requests, [])
            finally:
                device.close()

    def test_clear_failures_protect_without_retry(self):
        for fault in ('write_bus', 'write_timeout', 'verify_mismatch', 'enable_timeout'):
            device = Device(fault=fault)
            try:
                result = device.run('mpc-mpcx-ip-writer', '127.0.0.1', '--clear')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Success!', result.stdout)
                self.assertEqual(device.memory[0xFFFFFCFF], 255)
                writes = [request for request in device.requests if request[0] == 0x80]
                self.assertEqual(writes[-1], (0x80, 0xFFFFFCFF, 1))
                self.assertEqual(writes.count((0x80, 0xFFFFFCFF, 1)), 2)
                self.assertEqual(writes.count((0x80, 0xFFFFFC20, 16)),
                                 0 if fault == 'enable_timeout' else 1)
                times = [when for when, request in zip(device.request_times, device.requests)
                         if request[0] == 0x80]
                for earlier, later in zip(times, times[1:]):
                    self.assertGreaterEqual(later - earlier, 0.45)
            finally:
                device.close()

    def test_advanced_clear_guard_preserved(self):
        device = Device()
        try:
            result = device.run('mpc-mpcx-ip-command', 'clear', '127.0.0.1')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('--yes-really-clear', result.stderr)
            self.assertEqual(device.requests, [])
        finally:
            device.close()


if __name__ == '__main__':
    unittest.main()
