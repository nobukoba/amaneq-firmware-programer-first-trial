"""Read-only Check and native forced-initialization regression tests."""
import json
import tempfile
from pathlib import Path
import unittest

from test_register_report import Device
from test_mpc_programming import ROOT, PAYLOAD, region, write_payload


class WriterModeTests(unittest.TestCase):
    def test_xg_writes_and_failure_cleanup_wait_500ms(self):
        reference = json.loads((ROOT / 'tests/reference/official_xg_forced.json').read_text())
        for fault, options in ((None, ()), ('extension_bus', ('--initialize-eeprom',)),
                               ('extension_bus', ('--initialize-eeprom', '--write-chunk-size', '16')),
                               ('write_bus', ('--initialize-eeprom', '--write-chunk-size', '16')),
                               ('enable_timeout', ())):
            device = Device(xg=True, fault=fault)
            try:
                p = write_payload(device, bytes.fromhex(reference['synthetic_payload']), *options)
                self.assertEqual(p.returncode == 0, fault not in ('write_bus', 'enable_timeout'), p.stderr)
                times = [when for when, request in zip(device.request_times, device.requests)
                         if request[0] == 0x80]
                self.assertGreaterEqual(len(times), 2)
                for before, after in zip(times, times[1:]):
                    self.assertGreaterEqual(after - before, 0.49)
                self.assertEqual(device.memory[0xFFFFFCFF], 255)
            finally:
                device.close()

    def test_check_reads_only_native_identifier_and_status(self):
        for xg in (False, True):
            for control in (0, 128):
                device = Device(xg=xg)
                try:
                    device.memory[0xFFFFFC10] = control
                    before = dict(device.memory)
                    p = device.run('mpc-mpcx-ip-writer', '127.0.0.1', '--check')
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertEqual(device.requests,
                                     [(192, 0xFFFFFF08, 4), (192, 0xFFFFFC10, 1)])
                    self.assertEqual(device.memory, before)
                    self.assertEqual(p.stdout,
                                     'MPC(X) File : Not Selected.\nDevice 127.0.0.1 : ' +
                                     ('SiTCP XG' if xg else 'SiTCP 100/1000M') +
                                     '\n' + ('EEOROM needs to be inbitialized.' if control else
                                             'EEPROM was already initialized') + '\n')
                    self.assertNotIn('Success!', p.stdout)
                finally:
                    device.close()

    def test_check_file_generation_match_and_mismatch(self):
        for xg in (False, True):
            device = Device(xg=xg)
            try:
                p = write_payload(device, PAYLOAD, '--check')
                self.assertEqual(p.returncode, 7 if xg else 0, p.stderr)
                self.assertEqual(p.stdout,
                                 'MPC(X) File : Other\n  Interface : 100/1000MbE\n'
                                 'Device 127.0.0.1 : ' + ('SiTCP XG - Mismatch' if xg else
                                                        'SiTCP 100/1000M - Matched') +
                                 '\nEEPROM was already initialized\n')
                self.assertFalse(device.write_packets)
            finally:
                device.close()

    def test_invalid_mode_combinations_before_access(self):
        combinations = [('--check', '--clear'), ('--check', '--initialize-eeprom'),
                        ('--check', '--set-current-ip', '192.0.2.1'),
                        ('--check', '--set-eeprom-ip', '192.0.2.1'),
                        ('--check', '--no-fallback'),
                        ('--check', '--write-chunk-size', 'official'),
                        ('--clear', '--initialize-eeprom'), ('--initialize-eeprom',)]
        for options in combinations:
            device = Device()
            try:
                p = device.run('mpc-mpcx-ip-writer', '127.0.0.1', *options)
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(device.requests, [])
            finally:
                device.close()

    def test_check_xg_file_and_decoded_label(self):
        reference = json.loads((ROOT / 'tests/reference/official_xg_forced.json').read_text())
        for xg in (False, True):
            for control in (0, 128):
                device = Device(xg=xg)
                try:
                    device.memory[0xFFFFFC10] = control
                    p = write_payload(device, bytes.fromhex(reference['synthetic_payload']), '--check')
                    self.assertEqual(p.returncode, 0 if xg else 7, p.stderr)
                    self.assertEqual(p.stdout,
                                     'MPC(X) File : Other\n  Interface : 10GbE\nDevice 127.0.0.1 : ' +
                                     ('SiTCP XG - Matched' if xg else 'SiTCP 100/1000M - Mismatch') +
                                     '\n' + ('EEOROM needs to be inbitialized.' if control else
                                             'EEPROM was already initialized') + '\n')
                    self.assertFalse(device.write_packets)
                finally:
                    device.close()

    def test_forced_xg_split_and_ip_override(self):
        reference = json.loads((ROOT / 'tests/reference/official_xg_forced.json').read_text())
        device = Device(xg=True, fault='extension_bus')
        try:
            device.put(0xFFFFFF00, bytes.fromhex(reference['runtime_before']))
            device.put(0xFFFFFC00, bytes.fromhex(reference['eeprom_before']))
            runtime = region(device, 0xFFFFFF00, 80)
            p = write_payload(device, bytes.fromhex(reference['synthetic_payload']),
                              '--initialize-eeprom', '--write-chunk-size', '16',
                              '--set-eeprom-ip', '192.168.10.11')
            self.assertEqual(p.returncode, 0, p.stderr)
            expected = bytearray.fromhex(reference['eeprom_after'])
            expected[24:28] = bytes([192, 168, 10, 11])
            self.assertEqual(region(device, 0xFFFFFC00, 128), expected)
            self.assertEqual(region(device, 0xFFFFFF00, 80), runtime)
            data = [(a, len(b)) for a, b in device.write_packets if a != 0xFFFFFCFF]
            self.assertEqual(data[:5], [(0xFFFFFC00 + i, 16) for i in range(0, 80, 16)])
            self.assertEqual(data[5:], [(0xFFFFFC00, 17), (0xFFFFFC18, 40)])
            self.assertEqual(device.memory[0xFFFFFCFF], 255)
        finally:
            device.close()

    def test_check_invalid_file_and_read_failures_never_write(self):
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / 'invalid.mpc'
            invalid.write_bytes(b'bad')
            device = Device()
            try:
                p = device.run('mpc-mpcx-ip-writer', '127.0.0.1', str(invalid), '--check')
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(device.requests, [])
            finally:
                device.close()
        for fault in ('identifier_timeout', 'check_control_bus'):
            device = Device(fault=fault)
            try:
                p = device.run('mpc-mpcx-ip-writer', '127.0.0.1', '--check')
                self.assertNotEqual(p.returncode, 0)
                self.assertFalse(device.write_packets)
            finally:
                device.close()

    def test_initialize_option_matches_native_for_both_generations(self):
        for generation in ('normal', 'xg'):
            reference = json.loads((ROOT / 'tests/reference' /
                                   ('official_' + generation + '_forced.json')).read_text())
            device = Device(xg=generation == 'xg', fault='extension_bus')
            try:
                device.put(0xFFFFFF00, bytes.fromhex(reference['runtime_before']))
                device.put(0xFFFFFC00, bytes.fromhex(reference['eeprom_before']))
                p = write_payload(device, bytes.fromhex(reference['synthetic_payload']),
                                  '--initialize-eeprom')
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(region(device, 0xFFFFFC00, 128),
                                 bytes.fromhex(reference['eeprom_after']))
                self.assertEqual([(f'{a:08X}', data.hex()) for a, data in device.write_packets
                                  if a != 0xFFFFFCFF],
                                 [(reference['data_write_address'], reference['data_write_payload'])])
                self.assertEqual(device.memory[0xFFFFFCFF], 255)
            finally:
                device.close()

    def test_forced_xg_still_requires_complete_safe_ram(self):
        reference = json.loads((ROOT / 'tests/reference/official_xg_forced.json').read_text())
        for fault in ('short', 'bus', 'write_bus', 'enable_timeout'):
            device = Device(xg=True, fault=fault)
            try:
                p = write_payload(device, bytes.fromhex(reference['synthetic_payload']),
                                  '--initialize-eeprom', '--no-fallback')
                self.assertNotEqual(p.returncode, 0)
                if fault in ('short', 'bus'):
                    self.assertFalse(device.write_packets)
                else:
                    self.assertEqual(device.memory[0xFFFFFCFF], 255)
            finally:
                device.close()


if __name__ == '__main__':
    unittest.main()
