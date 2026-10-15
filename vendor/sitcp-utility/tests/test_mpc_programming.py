"""Normal MPC compatibility, using actual official-GUI synthetic-data evidence."""
import json
import pathlib
import tempfile
import unittest

from test_register_report import Device

ROOT = pathlib.Path(__file__).resolve().parents[1]
REFERENCE = json.loads((ROOT / 'tests/reference/official_mpc_erased.json').read_text())
PAYLOAD = bytes.fromhex(REFERENCE['synthetic_payload'])


def region(device, base, length):
    return bytes(device.memory.get(base + i, 0) for i in range(length))


def write_payload(device, payload, *options):
    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / 'synthetic.mpc'
        path.write_bytes(payload)
        return device.run('mpc-mpcx-ip-writer', '127.0.0.1', str(path), *options)


def write_mpc(device, *options):
    return write_payload(device, PAYLOAD, *options)


class MpcProgrammingTests(unittest.TestCase):
    def test_bulk_and_16_byte_modes_have_identical_images(self):
        xg_reference = json.loads((ROOT / 'tests/reference/official_mpcx_erased.json').read_text())
        xg_payload = bytes.fromhex(xg_reference['synthetic_payload'])
        for xg, erased, base, size in ((False, False, 0xFFFFFC10, 64),
                                      (True, False, 0xFFFFFC00, 24),
                                      (True, True, 0xFFFFFC00, 80)):
            results = []
            sent = []
            for options in ((), ('--write-chunk-size', 'official'), ('--write-chunk-size', '16')):
                device = Device(xg=xg)
                try:
                    if erased:
                        device.put(0xFFFFFC00, bytes([255] * 128))
                    result = write_payload(device, xg_payload if xg else PAYLOAD, *options)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    data = [(address, payload) for address, payload in device.write_packets
                            if address != 0xFFFFFCFF]
                    expected_lengths = [size] if options != ('--write-chunk-size', '16') else [min(16, size-i) for i in range(0,size,16)]
                    self.assertEqual([len(payload) for _, payload in data], expected_lengths)
                    self.assertEqual([address for address, _ in data],
                                     [base] if options != ('--write-chunk-size', '16') else [base+i for i in range(0,size,16)])
                    sent.append(b''.join(payload for _, payload in data))
                    results.append(region(device, 0xFFFFFC00, 128))
                    self.assertEqual(device.memory[0xFFFFFCFF], 255)
                finally:
                    device.close()
            self.assertTrue(all(image == results[0] for image in results))
            self.assertTrue(all(data == sent[0] for data in sent))

    def test_invalid_chunk_options_abort_before_device_access(self):
        for options in (('--write-chunk-size','0'), ('--write-chunk-size','256'),
                        ('--write-chunk-size','-1'), ('--write-chunk-size','16x'),
                        ('--write-chunk-size',), ('--clear','--write-chunk-size','16'),
                        ('--clear','--write-chunk-size','official'), ('--clear','--no-fallback')):
            device = Device(xg=False)
            try:
                result = write_mpc(device, *options)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(device.requests, [])
            finally:
                device.close()

    def test_split_xg_failure_restores_protection_without_retry(self):
        reference = json.loads((ROOT / 'tests/reference/official_mpcx_erased.json').read_text())
        for fault in ('write_bus', 'write_timeout', 'verify_mismatch', 'enable_timeout'):
            device = Device(xg=True, fault=fault)
            try:
                device.put(0xFFFFFC00, bytes([255] * 128))
                result = write_payload(device, bytes.fromhex(reference['synthetic_payload']),
                                       '--write-chunk-size', '16')
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(device.memory[0xFFFFFCFF], 255)
                writes = [r for r in device.requests if r[0] == 0x80]
                self.assertEqual(writes[-1], (0x80,0xFFFFFCFF,1))
                self.assertEqual(writes.count((0x80,0xFFFFFC20,16)),
                                 0 if fault == 'enable_timeout' else 1)
            finally:
                device.close()

    def test_normal_write_pacing_matches_observed_reference(self):
        device = Device(xg=False)
        try:
            result = write_mpc(device)
            self.assertEqual(result.returncode, 0, result.stderr)
            writes = [(when, request) for when, request in
                      zip(device.request_times, device.requests) if request[0] == 0x80]
            self.assertEqual(len(writes), 3)
            self.assertGreaterEqual(writes[1][0] - writes[0][0], 0.45)
            self.assertGreaterEqual(writes[2][0] - writes[1][0], 0.45)
        finally:
            device.close()

    def test_mpc_images_match_official_captures(self):
        for name in ('official_mpc_erased.json', 'official_mpc_preserved.json'):
            with self.subTest(reference=name):
                reference = json.loads((ROOT / 'tests/reference' / name).read_text())
                device = Device(xg=False)
                try:
                    device.put(0xFFFFFF00, bytes.fromhex(reference['runtime_before']))
                    device.put(0xFFFFFC00, bytes.fromhex(reference['eeprom_before']))
                    result = write_payload(device, bytes.fromhex(reference['synthetic_payload']))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(region(device, 0xFFFFFC00, 128),
                                     bytes.fromhex(reference['eeprom_after']))
                    data_writes = [request for request in device.requests
                                   if request[0] == 0x80 and request[1] != 0xFFFFFCFF]
                    self.assertEqual(data_writes, [(0x80, 0xFFFFFC10, 64)])
                    self.assertEqual(device.memory[0xFFFFFCFF], 255)
                finally:
                    device.close()

    def test_mpcx_image_matches_official_capture(self):
        reference = json.loads((ROOT / 'tests/reference/official_mpcx_erased.json').read_text())
        # The captured native reference rejected all optional extension reads.
        device = Device(xg=True, fault='extension_bus')
        try:
            device.put(0xFFFFFF00, bytes.fromhex(reference['runtime_before']))
            device.put(0xFFFFFC00, bytes.fromhex(reference['eeprom_before']))
            result = write_payload(device, bytes.fromhex(reference['synthetic_payload']))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(region(device, 0xFFFFFC00, 128),
                             bytes.fromhex(reference['eeprom_after']))
            self.assertEqual([r for r in device.requests if r[0] == 0x80 and r[1] != 0xFFFFFCFF],
                             [(0x80, 0xFFFFFC00, 80)])
            self.assertEqual(device.memory[0xFFFFFCFF], 255)
        finally:
            device.close()

    def test_initialized_settings_and_reserved_regions_preserved(self):
        device = Device(xg=False)
        try:
            before = region(device, 0xFFFFFC00, 128)
            expected = bytearray(before)
            expected[0x10] = 1
            expected[0x12:0x18] = PAYLOAD[:6]
            expected[0x40:0x50] = PAYLOAD[6:]
            result = write_mpc(device)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(region(device, 0xFFFFFC00, 128), bytes(expected))
            self.assertFalse(any(address == 0xFFFFFF18 and length == 40
                                 for _, address, length in device.requests))
            self.assertFalse(any(address == 0xFFFFFC00
                                 for _, address, _ in device.requests))
        finally:
            device.close()

    def test_normal_initialization_uses_ip_endpoints_not_mpcx_bit(self):
        for control, ip, initialize in (
            (0x80, bytes([192, 0, 2, 10]), False),
            (0x00, bytes([255, 0, 2, 255]), True),
            (0x80, bytes([255, 0, 2, 10]), False),
            (0x80, bytes([192, 0, 2, 255]), False),
        ):
            with self.subTest(control=control, ip=ip):
                device = Device(xg=False)
                try:
                    device.memory[0xFFFFFC10] = control
                    device.put(0xFFFFFC18, ip)
                    result = write_mpc(device)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(device.memory[0xFFFFFC10], 1)
                    self.assertEqual(region(device, 0xFFFFFC18, 4),
                                     region(device, 0xFFFFFF18, 4) if initialize else ip)
                    self.assertEqual(any(address == 0xFFFFFF18 and length == 40
                                         for _, address, length in device.requests), initialize)
                finally:
                    device.close()

    def test_unreadable_ram_stops_before_any_write(self):
        for fault in ('mpc_ram_bus', 'mpc_ram_timeout', 'mpc_ram_short'):
            device = Device(xg=False, fault=fault)
            try:
                device.put(0xFFFFFC00, bytes([255] * 128))
                result = write_mpc(device, '--no-fallback')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('No EEPROM writes performed', result.stderr)
                self.assertFalse(any(command == 0x80 for command, _, _ in device.requests))
            finally:
                device.close()

    def test_normal_unreadable_ram_uses_complete_official_defaults(self):
        reference = json.loads(
            (ROOT / 'tests/reference/official_mpc_fallback.json').read_text())
        expected = bytes.fromhex(
            'c0a80a100018001705b4123403e8ea6013882bf201f401f43000'
            '0000000000000000000000000000')
        self.assertEqual(len(expected), 40)
        for fault in ('mpc_ram_bus', 'mpc_ram_timeout', 'mpc_ram_short'):
            device = Device(xg=False, fault=fault)
            try:
                device.put(0xFFFFFC00, bytes([255] * 128))
                result = write_mpc(device)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(region(device, 0xFFFFFC18, 40), expected)
                self.assertEqual(device.memory[0xFFFFFC11], 0)
                self.assertEqual(region(device, 0xFFFFFC12, 6), PAYLOAD[:6])
                self.assertEqual(region(device, 0xFFFFFC40, 16), PAYLOAD[6:])
                self.assertEqual(device.memory[0xFFFFFCFF], 255)
                self.assertEqual(region(device, 0xFFFFFC00, 128),
                                 bytes.fromhex(reference['eeprom_after']))
                self.assertEqual(
                    [data.hex() for address, data in device.write_packets
                     if address == 0xFFFFFC10],
                    [reference['data_write_payload']])
            finally:
                device.close()

    def test_write_failures_restore_protection_without_retry(self):
        for fault in ('mpc_write_bus', 'mpc_write_timeout',
                      'mpc_verify_mismatch', 'enable_timeout'):
            device = Device(xg=False, fault=fault)
            try:
                result = write_mpc(device)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('Success!', result.stdout)
                self.assertEqual(device.memory[0xFFFFFCFF], 255)
                writes = [request for request in device.requests if request[0] == 0x80]
                self.assertEqual(writes[-1], (0x80, 0xFFFFFCFF, 1))
                self.assertEqual(writes.count((0x80, 0xFFFFFC10, 64)),
                                 0 if fault == 'enable_timeout' else 1)
            finally:
                device.close()

    def test_ip_overrides_follow_programming(self):
        device = Device(xg=False)
        try:
            device.put(0xFFFFFC00, bytes([255] * 128))
            result = write_mpc(device, '--set-eeprom-ip', '192.0.2.42',
                               '--set-current-ip', '127.0.0.1')
            self.assertEqual(result.returncode, 0, result.stderr)
            writes = [request for request in device.requests if request[0] == 0x80]
            self.assertLess(writes.index((0x80, 0xFFFFFC10, 64)),
                            writes.index((0x80, 0xFFFFFC18, 40)))
            self.assertLess(writes.index((0x80, 0xFFFFFC18, 40)),
                            writes.index((0x80, 0xFFFFFF18, 40)))
        finally:
            device.close()


if __name__ == '__main__':
    unittest.main()
