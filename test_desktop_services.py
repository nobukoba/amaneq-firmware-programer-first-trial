import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import desktop_services as desktop
import macos_network as net

ROOT = Path(__file__).parent


class DesktopTests(unittest.TestCase):
    def test_cable_selection_requires_exact_serial_and_model(self):
        found = [
            {"serial": "A", "vidpid": "0403:6014", "cable": None},
            {"serial": "B", "vidpid": "0403:6014", "cable": None},
        ]
        for selected, confirmed in [("", True), ("A", False), ("C", True)]:
            with self.assertRaises(ValueError):
                desktop.cable_arguments(selected, found, confirmed)
        self.assertEqual(
            desktop.cable_arguments("B", found, True),
            ["--cable", "hs3", "--serial", "B"],
        )
        with self.assertRaises(ValueError):
            desktop.cable_arguments("A", found + [found[0]], True)

    def test_latest_rows_use_hex_version_and_pin_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = desktop.DesktopServices(ROOT, Path(tmp))
            entries = [
                {"path": "mcs/amaneq-4-strlrtdc-v2.9.mcs"},
                {"path": "mcs/amaneq-4-strlrtdc-v2.A.mcs"},
                {"path": "bit/amaneq-4-strlrtdc-v2.B.bit"},
            ]
            github = Mock()
            github.get.return_value = {"default_branch": "main"}
            github.revision.return_value = "a" * 40
            github.files.return_value = entries
            with patch.object(service.core, "GitHub", return_value=github):
                rows = service._repository_rows("lrtdc", "AMANEQ-official/StrLrTdc")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "amaneq-4-strlrtdc-v2.A.mcs")
            self.assertEqual(rows[0]["commit"], "a" * 40)

    def test_offline_catalog_reports_stale_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "latest-images-v3.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "timestamp": 0,
                        "checked_at": "old date",
                        "rows": [{"name": "cached.mcs"}],
                    }
                )
            )
            service = desktop.DesktopServices(ROOT, root)
            with patch.object(
                service, "_repository_rows", side_effect=OSError("offline")
            ):
                rows, status, failures = service.catalog(force=True)
            self.assertIn("not refreshed", status)
            self.assertEqual(rows[0]["name"], "cached.mcs")
            self.assertEqual(len(failures), 9)

    def test_profile_image_list_filters_versions_and_caches_custom_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = desktop.DesktopServices(ROOT, Path(tmp))
            github = Mock()
            github.repo = "example/custom-firmware"
            github.get.return_value = {"default_branch": "main"}
            github.revision.return_value = "b" * 40
            github.files.return_value = [
                {"path": f"mcs/amaneq-4-strlrtdc-v2.{i:X}.mcs"} for i in range(12)
            ] + [
                {"path": "mcs/amaneq-1-strlrtdc-v3.0.mcs"},
                {"path": "mcs/amaneq-4-strhrtdc-v3.0.mcs"},
                {"path": "bit/amaneq-4-strlrtdc-v3.0.bit"},
            ]
            with patch.object(service.core, "GitHub", return_value=github):
                rows, status, errors = service.image_list(
                    github.repo, "amaneq-v4", "lrtdc"
                )
                self.assertEqual(len(rows), 10)
                self.assertEqual(rows[0]["name"], "amaneq-4-strlrtdc-v2.B.mcs")
                self.assertTrue(
                    all(
                        row["repo"] == github.repo and row["commit"] == "b" * 40
                        for row in rows
                    )
                )
                self.assertFalse(errors)
                github.get.side_effect = OSError("offline")
                cached, status, errors = service.image_list(
                    github.repo, "amaneq-v4", "lrtdc", force=True
                )
                self.assertEqual(cached, rows)
                self.assertIn("not refreshed", status)
                self.assertIn("offline", errors[0])
                with self.assertRaises(OSError):
                    service.image_list(github.repo, "amaneq-v1", "lrtdc", force=True)

    def test_history_recovers_replaced_versions_and_deduplicates_blobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = desktop.DesktopServices(ROOT, Path(tmp))
            github = Mock()
            github.repo = "example/history"
            github.get.return_value = {"default_branch": "main"}
            github.revision.return_value = "a" * 40
            commits = [
                {"sha": sha * 40, "commit": {"committer": {"date": date}}}
                for sha, date in [
                    ("a", "2026-10-16"),
                    ("b", "2026-10-15"),
                    ("c", "2026-10-14"),
                    ("d", "2026-10-13"),
                ]
            ]
            github.pages.side_effect = lambda endpoint, limit: (
                [{"name": "v2.9", "commit": {"sha": "c" * 40}}]
                if endpoint == "/tags"
                else commits
            )
            github.files.side_effect = lambda sha: (
                [{"path": "mcs/amaneq-4-strlrtdc-v2.A.mcs", "sha": "same"}]
                if sha[0] in "ab"
                else (
                    [{"path": "mcs/amaneq-4-strlrtdc-v2.9.mcs", "sha": "old"}]
                    if sha[0] == "c"
                    else [{"path": "mcs/amaneq-4-strlrtdc-v2.8.mcs", "sha": "older"}]
                )
            )
            with patch.object(service.core, "GitHub", return_value=github):
                rows, status, errors = service.image_list(
                    github.repo,
                    "amaneq-v4",
                    "lrtdc",
                    include_history=True,
                    history_limit=3,
                )
            self.assertEqual(
                [row["name"] for row in rows],
                [
                    "amaneq-4-strlrtdc-v2.A.mcs",
                    "amaneq-4-strlrtdc-v2.9.mcs",
                    "amaneq-4-strlrtdc-v2.8.mcs",
                ],
            )
            self.assertEqual(rows[1]["commit"], "c" * 40)
            self.assertEqual(rows[1]["revision"], "v2.9")
            self.assertFalse(errors)
            self.assertTrue(rows[0]["is_current"])


class NetworkTests(unittest.TestCase):
    def test_ethernet_picker_excludes_wifi_and_bridge(self):
        text = "Hardware Port: USB 10/100/1000 LAN\nDevice: en7\nEthernet Address: aa:bb:cc:dd:ee:ff\n\nHardware Port: Wi-Fi\nDevice: en0\n\nHardware Port: Thunderbolt Bridge\nDevice: bridge0\n"
        with (
            patch.object(net.sys, "platform", "darwin"),
            patch.object(net, "run", return_value=text),
        ):
            self.assertEqual(
                net.ethernet_adapters(),
                [{"interface": "en7", "name": "USB 10/100/1000 LAN"}],
            )

    def test_hex_netmask_parser(self):
        self.assertEqual(
            net.parse_addresses(
                "en7: flags\n inet 192.168.10.70 netmask 0xffffff00 broadcast 192.168.10.255\n"
            ),
            [{"interface": "en7", "address": "192.168.10.70", "mask": "255.255.255.0"}],
        )

    def test_alias_validation_preserves_existing_addresses(self):
        existing = [
            {"interface": "en7", "address": "192.168.10.71", "mask": "255.255.255.0"}
        ]
        self.assertEqual(
            net.validate_configuration(
                "en7", "192.168.10.70", "255.255.255.0", existing
            )[2],
            "255.255.255.255",
        )
        for interface, ip, mask, values in [
            ("en7", "192.168.10.71", "255.255.255.0", existing),
            ("en8", "192.168.10.70", "255.255.255.0", existing),
            ("en7;bad", "192.168.10.70", "255.255.255.0", []),
            ("en7", "192.168.10.0", "255.255.255.0", []),
            ("en7", "127.0.0.1", "255.255.255.0", []),
            ("en7", "192.168.10.70", "255.0.255.0", []),
        ]:
            with self.assertRaises(net.NetworkError):
                net.validate_configuration(interface, ip, mask, values)

    def test_remove_only_exact_owned_alias(self):
        data = {
            "interface": "en7",
            "address": "192.168.10.70",
            "effective_mask": "255.255.255.0",
            "mac": "aa:bb:cc:dd:ee:ff",
        }
        current = [
            {"interface": "en7", "address": "192.168.10.70", "mask": "255.255.255.0"}
        ]
        with (
            patch.object(net, "all_addresses", side_effect=[current, current, []]),
            patch.object(net, "interface_mac", return_value=data["mac"]),
            patch.object(net, "run") as run,
        ):
            net.remove_alias(data)
        run.assert_called_once_with(
            ["/sbin/ifconfig", "en7", "inet", "192.168.10.70", "-alias"]
        )
        with (
            patch.object(net, "all_addresses", return_value=current),
            patch.object(net, "interface_mac", return_value="00:00:00:00:00:00"),
            patch.object(net, "run") as run,
        ):
            with self.assertRaises(net.NetworkError):
                net.remove_alias(data)
            run.assert_not_called()

    def test_guard_failure_rolls_back_new_alias(self):
        data = {
            "interface": "en7",
            "address": "192.168.10.70",
            "mask": "255.255.255.0",
            "effective_mask": "255.255.255.0",
            "mac": "aa:bb:cc:dd:ee:ff",
            "parent_pid": 123,
            "parent_identity": "birth",
            "release": False,
        }
        present = []

        def execute(arguments):
            if arguments[-1] == "alias":
                present.append(
                    {
                        "interface": "en7",
                        "address": data["address"],
                        "mask": data["mask"],
                    }
                )
            elif arguments[-1] == "-alias":
                present.clear()
            return ""

        with (
            patch.object(net.sys, "platform", "darwin"),
            patch.object(net.os, "geteuid", return_value=0, create=True),
            patch.object(net, "read_lease", return_value=data),
            patch.object(net, "process_identity", return_value="birth"),
            patch.object(net, "interface_mac", return_value=data["mac"]),
            patch.object(
                net, "all_addresses", side_effect=lambda: copy.deepcopy(present)
            ),
            patch.object(net, "run", side_effect=execute),
            patch.object(
                net.subprocess, "Popen", side_effect=OSError("cannot start guard")
            ),
        ):
            with self.assertRaises(OSError):
                net.privileged("apply", Path("unused"), ["app"])
        self.assertEqual(present, [])

    def test_guard_cleans_up_after_parent_exit(self):
        data = {"token": "a" * 32, "parent_pid": 123, "parent_identity": "birth"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lease.json"
            path.write_text(json.dumps({**data, "release": False}))
            with (
                patch.object(net.sys, "platform", "darwin"),
                patch.object(net.os, "geteuid", return_value=0, create=True),
                patch.object(net, "read_lease", return_value=data),
                patch.object(net, "process_identity", side_effect=["birth", ""]),
                patch.object(net.time, "sleep"),
                patch.object(net, "remove_alias") as remove,
            ):
                net.privileged("guard", path, ["app"])
            remove.assert_called_once_with(data)


if __name__ == "__main__":
    unittest.main()
