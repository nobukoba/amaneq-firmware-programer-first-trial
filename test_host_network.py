"""Offline checks for temporary address ownership, rollback and platform boundaries."""

import ctypes
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import host_network as net


def lease():
    return dict(
        interface="eth0",
        address="192.168.10.20",
        mask="255.255.255.0",
        effective_mask="255.255.255.0",
        mac="02:00:00:00:00:01",
        parent_pid=1234,
        parent_identity="created",
        token="a" * 32,
        release=False,
    )


class TemporaryNetworkTests(unittest.TestCase):
    def setUp(self):
        self.platform = patch.object(net.sys, "platform", "linux")
        self.windows = patch.object(net, "IS_WINDOWS", False)
        self.platform.start()
        self.windows.start()
        self.addCleanup(self.platform.stop)
        self.addCleanup(self.windows.stop)

    def test_duplicate_and_other_adapter_overlap_stop_before_writes(self):
        existing = [
            dict(interface="eth1", address="192.168.10.30", mask="255.255.255.0")
        ]
        for address in ("192.168.10.30", "192.168.10.20"):
            with self.assertRaises(net.NetworkError):
                net.validate_configuration("eth0", address, "255.255.255.0", existing)
        with self.assertRaises(net.NetworkError):
            net.validate_configuration("eth0;touch /tmp/no", "192.168.10.20", "24", [])

    def test_same_subnet_uses_host_mask_without_replacing_existing_route(self):
        existing = [
            dict(interface="eth0", address="192.168.10.30", mask="255.255.255.0")
        ]
        self.assertEqual(
            net.validate_configuration("eth0", "192.168.10.20", "24", existing)[2],
            "255.255.255.255",
        )

    def test_linux_add_delete_are_scoped_to_one_address(self):
        with (
            patch.object(net, "ip_command", return_value="/usr/sbin/ip"),
            patch.object(net.mac, "run") as run,
        ):
            net.change_address("add", lease())
            self.assertEqual(
                run.call_args.args[0],
                ["/usr/sbin/ip", "address", "add", "192.168.10.20/24", "dev", "eth0"],
            )
            net.change_address("del", lease())
            self.assertEqual(run.call_args.args[0][2], "del")

    def test_changed_mac_or_mask_refuses_removal(self):
        for identity, mask in [
            ("02:00:00:00:00:02", "255.255.255.0"),
            ("02:00:00:00:00:01", "255.255.0.0"),
        ]:
            with (
                patch.object(net, "alias_present", return_value=True),
                patch.object(net, "adapter_identity", return_value=identity),
                patch.object(
                    net,
                    "normalized_addresses",
                    return_value=[{**lease(), "mask": mask}],
                ),
                patch.object(net, "change_address") as change,
            ):
                with self.assertRaises(net.NetworkError):
                    net.remove_alias(lease())
                change.assert_not_called()

    def test_failed_add_does_not_remove_someone_elses_address(self):
        with (
            patch.object(net.os, "geteuid", return_value=0, create=True),
            patch.object(net, "read_lease", return_value=lease()),
            patch.object(net, "process_identity", return_value="created"),
            patch.object(net, "normalized_addresses", return_value=[]),
            patch.object(net, "adapter_identity", return_value=lease()["mac"]),
            patch.object(
                net, "change_address", side_effect=net.NetworkError("already exists")
            ),
            patch.object(net, "remove_alias") as remove,
        ):
            with self.assertRaisesRegex(net.NetworkError, "already exists"):
                net.privileged("apply", Path("/unused"), ["app"])
            remove.assert_not_called()

    def test_failed_guard_start_rolls_back_owned_address(self):
        child = Mock()
        child.poll.return_value = 1
        with (
            patch.object(net.os, "geteuid", return_value=0, create=True),
            patch.object(net, "read_lease", return_value=lease()),
            patch.object(net, "process_identity", return_value="created"),
            patch.object(net, "normalized_addresses", return_value=[]),
            patch.object(net, "adapter_identity", return_value=lease()["mac"]),
            patch.object(net, "change_address"),
            patch.object(net, "alias_present", return_value=True),
            patch.object(net.subprocess, "Popen", return_value=child),
            patch.object(net.time, "sleep"),
            patch.object(net, "remove_alias") as remove,
        ):
            with self.assertRaisesRegex(net.NetworkError, "cleanup helper"):
                net.privileged("apply", Path("/unused"), ["app"])
            remove.assert_called_once_with(lease())
            snapshot = json.loads(child.stdin.write.call_args.args[0])
            self.assertEqual(snapshot["mac"], lease()["mac"])

    def test_guard_parent_exit_removes_snapshot_address(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ("a" * 32 + ".json")
            with (
                patch.object(net.os, "geteuid", return_value=0, create=True),
                patch.object(net.sys, "stdin", io.StringIO(json.dumps(lease()) + "\n")),
                patch.object(net, "process_identity", return_value="different process"),
                patch.object(net, "remove_alias") as remove,
            ):
                net.privileged("guard", path, ["app"])
                remove.assert_called_once_with(lease())
                self.assertTrue(
                    json.loads(path.with_suffix(".result").read_text())["success"]
                )

    def test_no_apply_confirmation_prevents_fallback_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lease.json"
            net.save(path, lease())
            with (
                patch.object(net, "alias_present", return_value=True),
                patch.object(net.time, "sleep"),
                patch.object(net, "authorize") as authorize,
            ):
                with self.assertRaisesRegex(net.NetworkError, "ownership"):
                    net.release(path, lease(), ["app"])
                authorize.assert_not_called()

    def test_mac_backend_remains_delegated(self):
        with (
            patch.object(net.sys, "platform", "darwin"),
            patch.object(
                net.mac, "ethernet_adapters", return_value=[{"interface": "en5"}]
            ) as adapters,
        ):
            self.assertEqual(net.ethernet_adapters(), [{"interface": "en5"}])
            adapters.assert_called_once()

    def test_windows_uses_ip_helper_and_waits_for_dad(self):
        library = Mock()
        library.CreateUnicastIpAddressEntry.return_value = 0
        library.GetUnicastIpAddressEntry.side_effect = lambda pointer: self.preferred(
            pointer
        )
        library.DeleteUnicastIpAddressEntry.return_value = 0
        data = {**lease(), "interface": "7"}
        with patch.object(net.ctypes, "WinDLL", return_value=library, create=True):
            net.windows_address("add", data)
            library.CreateUnicastIpAddressEntry.assert_called_once()
            library.DeleteUnicastIpAddressEntry.assert_not_called()
            net.windows_address("delete", data)
            library.DeleteUnicastIpAddressEntry.assert_called_once()

    @staticmethod
    def preferred(pointer):
        address = ctypes.cast(pointer, ctypes.c_void_p).value
        assert ctypes.c_uint32.from_address(address + 40).value == 7
        assert ctypes.c_ubyte.from_address(address + 60).value == 24
        assert ctypes.string_at(address + 4, 4) == bytes([192, 168, 10, 20])
        ctypes.c_uint32.from_address(address + 64).value = 4
        return 0

    def test_windows_dad_failure_rolls_back_only_successful_creation(self):
        library = Mock()
        library.CreateUnicastIpAddressEntry.return_value = 0
        library.GetUnicastIpAddressEntry.return_value = 87
        library.DeleteUnicastIpAddressEntry.return_value = 0
        with patch.object(net.ctypes, "WinDLL", return_value=library, create=True):
            with self.assertRaisesRegex(net.NetworkError, "duplicate-address"):
                net.windows_address("add", {**lease(), "interface": "7"})
            library.DeleteUnicastIpAddressEntry.assert_called_once()


if __name__ == "__main__":
    unittest.main()
