"""Integration checks using synthetic registers and a local RBCP device."""
import pathlib
import socket
import struct
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Device:
    def __init__(self, xg=True, rate=10000, fault=None):
        self.xg = xg
        self.memory = {}
        self.requests = []
        self.write_packets = []
        self.request_times = []
        self.fault = fault
        self.migrate_socket = None
        for base in (0xFFFFFF00, 0xFFFFFC00):
            for offset in range(80):
                self.memory[base + offset] = offset
        self.put(0xFFFFFF08, b'XTCP' if xg else b'SiTC')
        self.put(0xFFFFFF18, bytes([127, 0, 0, 1]))
        self.put(0xFFFFFC18, bytes([192, 0, 2, 10]))
        self.put(0xFFFFFF40, struct.pack('!H', rate))
        self.put(0xFFFFFC40, struct.pack('!H', 1000))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('127.0.0.1', 0))
        self.socket.settimeout(0.05)
        self.port = self.socket.getsockname()[1]
        self.running = True
        self.thread = threading.Thread(target=self.serve)
        self.thread.start()

    def put(self, address, data):
        self.memory.update((address + i, value) for i, value in enumerate(data))

    def serve(self):
        while self.running:
            try:
                packet, peer = self.socket.recvfrom(512)
            except socket.timeout:
                continue
            version, command, ident, length, address = struct.unpack('!BBBBI', packet[:8])
            self.requests.append((command, address, length))
            self.request_times.append(time.monotonic())
            if command == 0x80:
                self.write_packets.append((address, packet[8:]))
                self.put(address, packet[8:])
            data = bytes(self.memory.get(address + i, 0) for i in range(length))
            status = command | 8
            if command == 0xC0 and 0xFFFFFF50 <= address < 0xFFFFFF80:
                if any(address + i not in self.memory for i in range(length)):
                    status |= 1
                if self.fault == 'extension_bus' or (self.fault == 'extension_partial' and address == 0xFFFFFF60):
                    status |= 1
                if self.fault == 'extension_timeout':
                    continue
                if self.fault == 'extension_short':
                    data = data[:-1]
            if command == 0x80 and address == 0xFFFFFC50 and self.fault == 'extension_write_timeout':
                continue
            if self.fault and self.fault.startswith('utility_'):
                if command == 0xC0 and address in (0xFFFFFC00, 0xFFFFFF00) and length == 64:
                    if self.fault == 'utility_read_short':
                        data = data[:-1]
                    if self.fault == 'utility_read_bus':
                        status |= 1
                if command == 0x80 and address in (0xFFFFFC00, 0xFFFFFF00):
                    if self.fault == 'utility_prefix_timeout':
                        continue
                if command == 0x80 and address in (0xFFFFFC18, 0xFFFFFF18):
                    if self.fault == 'utility_parameters_timeout':
                        continue
                    if self.fault == 'utility_parameters_bus':
                        status |= 1
                    if self.fault == 'utility_verify_mismatch':
                        self.memory[address + 4] ^= 1
            if not self.xg and address < 0xFFFFFF50 and address + length > 0xFFFFFF40:
                status |= 1
            if self.fault == 'identifier_timeout' and address == 0xFFFFFF08:
                continue
            if self.fault == 'check_control_bus' and address == 0xFFFFFC10 and length == 1:
                status |= 1
            if command == 0x80 and address <= 0xFFFFFC20 < address + length:
                if self.fault == 'write_bus':
                    status |= 1
                if self.fault == 'write_timeout':
                    continue
                if self.fault == 'verify_mismatch':
                    self.memory[0xFFFFFC20] ^= 1
            if command == 0x80 and address == 0xFFFFFCFF and packet[8:] == b'\x00':
                if self.fault == 'enable_timeout':
                    continue
            if address <= 0xFFFFFF48 < address + length and self.fault == 'bus':
                status |= 1
            if self.fault == 'rate' and address <= 0xFFFFFF41 < address + length:
                status |= 1
            if self.fault == 'parameter' and address <= 0xFFFFFF23 < address + length:
                status |= 1
            if self.fault == 'eeprom' and address <= 0xFFFFFC40 < address + length:
                status |= 1
            if self.fault == 'block' and length == 8 and address == 0xFFFFFF40:
                status |= 1
            if address == 0xFFFFFF48 and self.fault == 'short':
                data = data[:-1]
            if address == 0xFFFFFF18 and length == 40:
                if self.fault == 'mpc_ram_bus':
                    status |= 1
                if self.fault == 'mpc_ram_timeout':
                    continue
                if self.fault == 'mpc_ram_short':
                    data = data[:-1]
            if command == 0x80 and address == 0xFFFFFC10 and length == 64:
                if self.fault == 'mpc_write_bus':
                    status |= 1
                if self.fault == 'mpc_write_timeout':
                    continue
                if self.fault == 'mpc_verify_mismatch':
                    self.memory[0xFFFFFC20] ^= 1
            self.socket.sendto(struct.pack('!BBBBI', version, status, ident, length, address) + data, peer)
            if command == 0x80 and address == 0xFFFFFF18 and self.migrate_socket is not None:
                old_socket = self.socket
                self.socket = self.migrate_socket
                self.migrate_socket = None
                old_socket.close()

    def close(self):
        self.running = False
        self.thread.join()
        self.socket.close()

    def run(self, program, *args):
        return subprocess.run(
            [str(ROOT / 'src' / program), *args, '--port', str(self.port), '--timeout', '0.1'],
            text=True, capture_output=True, timeout=10)


class ReportTests(unittest.TestCase):
    def test_optional_extensions(self):
        for fault in (None, 'extension_bus', 'extension_partial', 'extension_timeout',
                      'extension_short', 'extension_write_timeout'):
            device = Device(fault=fault)
            try:
                device.memory[0xFFFFFC10] = 255
                device.put(0xFFFFFF50, bytes(range(48)))
                device.put(0xFFFFFC50, bytes([170] * 48))
                with tempfile.TemporaryDirectory() as temp:
                    payload = pathlib.Path(temp) / 'synthetic.bin'
                    payload.write_bytes(bytes([0x2C] * 7 + [0] * 15))
                    result = device.run('mpc-mpcx-ip-writer', '127.0.0.1', str(payload))
                self.assertEqual(result.returncode == 0, fault != 'extension_write_timeout', result.stderr)
                self.assertEqual(device.memory[0xFFFFFCFF], 255)
                copies = [(a, d) for a, d in device.write_packets if 0xFFFFFC50 <= a < 0xFFFFFC80]
                if fault in ('extension_bus', 'extension_timeout', 'extension_short'):
                    self.assertEqual(copies, [])
                    self.assertEqual(bytes(device.memory[0xFFFFFC50+i] for i in range(48)), bytes([170]*48))
                elif fault == 'extension_partial':
                    self.assertEqual([a for a, _ in copies], [0xFFFFFC50, 0xFFFFFC70])
                elif fault == 'extension_write_timeout':
                    self.assertEqual(len(copies), 1)
                    self.assertNotIn('Success!', result.stdout)
                else:
                    self.assertEqual(bytes(device.memory[0xFFFFFC50+i] for i in range(48)), bytes(range(48)))
            finally:
                device.close()

    def test_unreachable_writer_does_not_write(self):
        device = Device()
        try:
            device.running = False
            device.thread.join()
            with tempfile.TemporaryDirectory() as temp:
                payload = pathlib.Path(temp) / 'synthetic.bin'
                payload.write_bytes(bytes([0x2C] * 7 + [0] * 15))
                started = time.monotonic()
                result = device.run('mpc-mpcx-ip-writer', '127.0.0.1', str(payload))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('timeout', result.stderr)
            self.assertLess(time.monotonic() - started, 3)
            self.assertEqual(device.write_packets, [])
            self.assertNotIn('Success!', result.stdout)
        finally:
            device.close()

    def test_generation_specific_parameters_and_units(self):
        for xg in (False, True):
            device = Device(xg=xg)
            try:
                for base, ip, disconnect in (
                    (0xFFFFFF00, bytes([198, 51, 100, 7]), 11250),
                    (0xFFFFFC00, bytes([203, 0, 113, 9]), 10000),
                ):
                    device.put(base + 0x1C, struct.pack('!H', 24))
                    device.put(base + 0x1E, struct.pack('!H', 23))
                    device.put(base + 0x20, struct.pack('!H', 1460))
                    device.put(base + 0x22, struct.pack('!H', 4660))
                    device.put(base + 0x2A, struct.pack('!H', disconnect))
                    device.put(base + 0x2C, struct.pack('!H', 500))
                    device.put(base + (0x32 if xg else 0x30), bytes([2, 0, 1, 2, 3, 4]))
                    device.put(base + (0x38 if xg else 0x36), ip)
                    device.put(base + (0x3C if xg else 0x3A), struct.pack('!H', 12345))
                    device.memory[base + 0x10] = 0x17 if xg else 0x49
                result = device.run('mpc-mpcx-ip-reader', '127.0.0.1')
                self.assertEqual(result.returncode, 0, result.stderr)
                runtime, eeprom = result.stdout.split('EEPROM (0xFFFFFC00', 1)
                for section, ip, seconds in (
                    (runtime, '198.51.100.7 (0xC6336407)', 2880.256 if xg else 2880.0),
                    (eeprom, '203.0.113.9 (0xCB007109)', 2560.256 if xg else 2560.0),
                ):
                    self.assertIn('TCP Port                            : 24 (0x0018)', section)
                    self.assertIn('UDP Port                            : 4660 (0x1234)', section)
                    self.assertIn('TCP Max Segment Size                : 1460 (0x05B4) bytes', section)
                    self.assertIn(f'({seconds:.3f} s,', section)
                    self.assertIn('server MAC                          : 02:00:01:02:03:04', section)
                    self.assertIn('server IP                           : ' + ip, section)
                    self.assertIn('server TCP port                     : 12345 (0x3039)', section)
                    self.assertIn('TCP Keep Alive Enabled              : ' +
                                  ('Enabled' if xg else 'Disabled'), section)
                    self.assertLess(section.index('TCP Keep Alive Enabled'),
                                    section.index('TCP Keep Alive(buffer not empty)'))
                    self.assertLess(section.index('TCP Keep Alive(buffer not empty)'),
                                    section.index('TCP Keep Alive(buffer empty)'))
                    if xg:
                        self.assertIn('TCP MSL                             : 500 (0x01F4) (250.0 ms)', section)
                        self.assertIn('window scaling                      : Enabled', section)
                    else:
                        self.assertIn('TCP Re-Connect Interval             : 500 (0x01F4) ms', section)
                        self.assertIn('TCP Command Port                    : 23 (0x0017)', section)
                        self.assertIn('client ARP                          : Enabled', section)
                        self.assertIn('MAC flow control                    : Enabled', section)
                self.assertTrue(all(command == 0xC0 for command, _, _ in device.requests))
            finally:
                device.close()

    def test_unreadable_normal_parameter_does_not_invent_value(self):
        device = Device(xg=False, fault='parameter')
        try:
            result = device.run('mpc-mpcx-ip-reader', '127.0.0.1')
            self.assertEqual(result.returncode, 3, result.stderr)
            runtime = result.stdout.split('EEPROM (0xFFFFFC00', 1)[0]
            self.assertIn('UDP Port                            : unavailable (RBCP bus error)', runtime)
            self.assertIn('TCP Max Segment Size                : 8225 (0x2021) bytes', runtime)
            self.assertIn('0xFFFFFF23', result.stderr)
            self.assertFalse(any(address + length > 0xFFFFFF40 and address >= 0xFFFFFF00
                                 for _, address, length in device.requests))
            self.assertTrue(all(command == 0xC0 for command, _, _ in device.requests))
        finally:
            device.close()

    def test_eeprom_ip_enable_timeout_restores_protection(self):
        device = Device(fault='enable_timeout')
        try:
            result = device.run('sitcp-sitcpxg-ip-writer', '127.0.0.1', '192.0.2.42')
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('Success!', result.stdout)
            self.assertEqual(device.memory[0xFFFFFCFF], 255)
            writes = [request for request in device.requests if request[0] == 0x80]
            self.assertEqual(writes, [(0x80, 0xFFFFFCFF, 1), (0x80, 0xFFFFFCFF, 1)])
        finally:
            device.close()

    def check_dump(self, output, device):
        runtime, eeprom = output.split('EEPROM (0xFFFFFC00', 1)
        self.assertIn('current IP          : 127.0.0.1 (0x7F000001)', runtime)
        self.assertIn('EEPROM IP           : 192.0.2.10 (0xC000020A)', eeprom)
        for base in (0xFFFFFF00, 0xFFFFFC00):
            length = 64 if base == 0xFFFFFF00 and not device.xg else 80
            for offset in range(0, length, 16):
                expected = ' '.join(f'{device.memory[base + offset + i]:02X}' for i in range(16))
                self.assertIn(f'{base + offset:08X}: {expected}', output)

    def test_read_views(self):
        for xg in (False, True):
            for program, args in (
                ('mpc-mpcx-ip-reader', ['127.0.0.1']),
                ('mpc-mpcx-ip-command', ['read', '127.0.0.1']),
                ('mpc-mpcx-ip-command', ['ip-read', '127.0.0.1']),
            ):
                with self.subTest(xg=xg, program=program, args=args):
                    device = Device(xg=xg)
                    try:
                        result = device.run(program, *args)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.check_dump(result.stdout, device)
                        self.assertEqual(result.stdout.count('\n\nTCP Port'), 2)
                        self.assertIn('\n\nraw runtime', result.stdout)
                        self.assertIn('\n\nraw EEPROM', result.stdout)
                        if xg:
                            self.assertIn('10000 (0x2710) Mbps', result.stdout)
                            self.assertIn('1000 (0x03E8) Mbps', result.stdout)
                            self.assertIn('10795 (0x2A2B)', result.stdout)
                        else:
                            self.assertIn('transmission rate                   : not supported (normal SiTCP)', result.stdout)
                            self.assertIn('0xFFFFFF00..0xFFFFFF3F, 64 bytes', result.stdout)
                            self.assertNotIn('FFFFFF40:', result.stdout)
                            self.assertNotIn('WARNING', result.stderr)
                            self.assertIn('COMPLETE', result.stdout)
                            self.assertFalse(any(
                                address < 0xFFFFFF50 and address + length > 0xFFFFFF40
                                for _, address, length in device.requests))
                        self.assertTrue(all(req[0] == 0xC0 for req in device.requests))
                        self.assertFalse(any(req[1] == 0xFFFFFF50 for req in device.requests))
                    finally:
                        device.close()

    def test_unknown_generation_does_not_guess_range(self):
        device = Device(fault='identifier_timeout')
        try:
            result = device.run('mpc-mpcx-ip-reader', '127.0.0.1')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('cannot select runtime read range', result.stderr)
            self.assertTrue(all(address == 0xFFFFFF08
                                for _, address, _ in device.requests))
        finally:
            device.close()

    def test_invalid_rate(self):
        device = Device(rate=65535)
        try:
            result = device.run('mpc-mpcx-ip-reader', '127.0.0.1')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('65535 (0xFFFF) (outside documented range', result.stdout)
            self.assertNotIn('65535 (0xFFFF) Mbps', result.stdout)
        finally:
            device.close()

    def test_incomplete_runtime_fails(self):
        for fault in ('short', 'bus'):
            device = Device(fault=fault)
            try:
                result = device.run('mpc-mpcx-ip-reader', '127.0.0.1')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('READ OK', result.stdout)
            finally:
                device.close()

    def test_partial_register_reports(self):
        for fault, address in (('bus', '0xFFFFFF48'), ('rate', '0xFFFFFF41'),
                               ('eeprom', '0xFFFFFC40')):
            for program, args in (
                ('mpc-mpcx-ip-reader', ['127.0.0.1']),
                ('mpc-mpcx-ip-command', ['read', '127.0.0.1']),
                ('mpc-mpcx-ip-command', ['ip-read', '127.0.0.1']),
            ):
                device = Device(fault=fault)
                try:
                    result = device.run(program, *args)
                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertIn(address, result.stderr)
                    self.assertIn('PARTIAL', result.stdout)
                    self.assertIn('raw EEPROM FC00..FC4F:', result.stdout)
                    self.assertIn('current IP          : 127.0.0.1', result.stdout)
                    self.assertIn('??', result.stdout)
                    if fault == 'rate':
                        runtime = result.stdout.split('EEPROM (0xFFFFFC00')[0]
                        self.assertIn('transmission rate                   : unavailable', runtime)
                        self.assertNotIn('10000 (0x2710)', runtime)
                        self.assertIn('FFFFFF40: 27 ?? 42 43 44 45 46 47', runtime)
                    if fault == 'eeprom':
                        self.assertIn('FFFFFC40: ?? E8 42 43', result.stdout)
                    self.assertTrue(all(req[0] == 0xC0 for req in device.requests))
                finally:
                    device.close()

    def test_block_error_byte_recovery(self):
        device = Device(fault='block')
        try:
            result = device.run('mpc-mpcx-ip-reader', '127.0.0.1')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.check_dump(result.stdout, device)
            self.assertIn('COMPLETE', result.stdout)
        finally:
            device.close()

    def test_partial_diagnostics_do_not_block_writer(self):
        device = Device(fault='rate')
        try:
            result = device.run('mpc-mpcx-ip-command', 'ip-write', '127.0.0.1', '192.0.2.20')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('PARTIAL', result.stdout)
            self.assertEqual(len(result.stdout.splitlines()), 7)
            self.assertIn('Success!', result.stdout)
            self.assertEqual(device.memory[0xFFFFFCFF], 255)
        finally:
            device.close()

    def test_writer_before_after(self):
        for xg in (False, True):
            device = Device(xg=xg)
            try:
                with tempfile.TemporaryDirectory() as temp:
                    payload = pathlib.Path(temp) / 'synthetic.bin'
                    payload.write_bytes(bytes([0x2C] * 7 + [0] * 15) if xg else bytes(22))
                    result = device.run('mpc-mpcx-ip-writer', '127.0.0.1', str(payload))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(result.stdout.splitlines()), 7)
                self.assertNotIn('raw runtime', result.stdout)
                self.assertIn('before: runtime MAC', result.stdout)
                self.assertIn('after:  EEPROM  MAC', result.stdout)
                if not xg:
                    self.assertNotIn('WARNING', result.stderr)
                    self.assertFalse(any(
                        address < 0xFFFFFF50 and address + length > 0xFFFFFF40
                        for _, address, length in device.requests))
                self.assertNotIn('raw EEPROM', result.stdout)
                self.assertEqual(device.memory[0xFFFFFCFF], 255)
                self.assertIn('Success!', result.stdout)
            finally:
                device.close()

    def test_standalone_ip_writer_compact(self):
        for current in (False, True):
            device = Device()
            try:
                args = ['127.0.0.1', '127.0.0.1' if current else '192.0.2.20']
                if current:
                    args.append('--current')
                result = device.run('sitcp-sitcpxg-ip-writer', *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(result.stdout.splitlines()), 7)
                self.assertIn('before: runtime MAC', result.stdout)
                self.assertIn('after:  EEPROM  MAC', result.stdout)
                self.assertIn('Success!', result.stdout)
                self.assertIn('(0x7F000001)', result.stdout)
            finally:
                device.close()

    def test_ip_writer_before_after(self):
        device = Device()
        try:
            result = device.run('mpc-mpcx-ip-command', 'ip-write', '127.0.0.1', '192.0.2.20')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(result.stdout.splitlines()), 7)
            self.assertNotIn('raw runtime', result.stdout)
            self.assertIn('192.0.2.20', result.stdout.split('after:', 1)[1])
            self.assertEqual(device.memory[0xFFFFFCFF], 255)
        finally:
            device.close()


if __name__ == '__main__':
    unittest.main()
