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
    def test_local_profile_uses_filename_not_hidden_github_selection(self):
        service = desktop.DesktopServices(ROOT, ROOT)
        for filename, board, expected in (
            ("amaneq-1-strlrtdc-v2.A.bit", "AMANEQ", ("amaneq-v1", "lrtdc")),
            ("amaneq-4-strhrtdc-v2.A.mcs", "AMANEQ", ("amaneq-v4", "hrtdc")),
            ("mzn-strhrtdc-v2.1.bit", "AMANEQ", ("hrtdc-mezzanine", "hrtdc")),
            ("cirasame-fw-v1.0.bit", "CIRASAME", ("cirasame", "skeleton")),
        ):
            self.assertEqual(service.local_profile(filename, board), expected)

    def test_local_profile_rejects_unknown_or_conflicting_board(self):
        service = desktop.DesktopServices(ROOT, ROOT)
        for filename, board in (
            ("renamed.bit", "AMANEQ"),
            ("amaneq-4-strlrtdc-v2.A.mcs", "CIRASAME"),
            ("cirasame-fw-v1.0.bit", "AMANEQ"),
            ("amaneq-4-strlrtdc-v2.A.mcs", "STAG"),
        ):
            with self.assertRaises(ValueError):
                service.local_profile(filename, board)

    def test_local_profile_shared_skeleton_uses_documented_compatible_profile(self):
        service = desktop.DesktopServices(ROOT, ROOT)
        self.assertEqual(
            service.local_profile("amaneq-skeleton-v2.2.bit", "AMANEQ"),
            ("amaneq-v4", "skeleton"),
        )

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
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["name"], "amaneq-4-strlrtdc-v2.A.mcs")
            self.assertEqual(rows[1]["name"], "amaneq-4-strlrtdc-v2.B.bit")
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
                self.assertEqual(len(rows), 5)
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

    def test_explicit_format_filters_all_families(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = desktop.DesktopServices(ROOT, Path(tmp))
            github = Mock()
            github.repo = "example/skeleton"
            github.get.return_value = {"default_branch": "main"}
            github.revision.return_value = "a" * 40
            github.files.return_value = [
                {"path": "bit/amaneq-skeleton-v2.2.bit"},
                {"path": "mcs/amaneq-skeleton-v2.2.mcs"},
            ]
            with patch.object(service.core, "GitHub", return_value=github):
                rows, status, errors = service.image_list(
                    github.repo, "amaneq-v4", "skeleton", image_format="bit"
                )
                self.assertEqual([row["format"] for row in rows], ["bit"])
                rows, status, errors = service.image_list(
                    github.repo, "amaneq-v4", "skeleton", image_format="mcs"
                )
                self.assertEqual([row["format"] for row in rows], ["mcs"])
                for family, stem in (
                    ("lrtdc", "strlrtdc"),
                    ("hrtdc", "strhrtdc"),
                    ("lrtdc-10g", "strlrtdc-10g"),
                    ("mikumari", "mch"),
                ):
                    github.files.return_value = [
                        {"path": f"bit/amaneq-4-{stem}-v2.2.bit"},
                        {"path": f"mcs/amaneq-4-{stem}-v2.2.mcs"},
                    ]
                    for kind in ("bit", "mcs"):
                        rows, status, errors = service.image_list(
                            github.repo, "amaneq-v4", family, image_format=kind
                        )
                        self.assertFalse(errors)
                        self.assertEqual([row["format"] for row in rows], [kind])


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


class GitHubAccessTests(unittest.TestCase):
    def test_metadata_cache_reuses_across_profiles_and_refreshes_mutable(self):
        from github_access import GitHubMetadata

        with tempfile.TemporaryDirectory() as directory:
            fetch = Mock(return_value={"sha": "abc"})
            cache = GitHubMetadata(directory, fetch)
            url = "https://api.github.com/repos/example/firmware"
            cache.get(url)
            cache.get(url)
            self.assertEqual(fetch.call_count, 1)
            cache.get(url, force=True)
            self.assertEqual(fetch.call_count, 2)
            pinned = url + "/git/trees/" + "a" * 40 + "?recursive=1"
            cache.get(pinned)
            cache.get(pinned, force=True)
            self.assertEqual(fetch.call_count, 3)

    def test_concurrent_metadata_reads_share_one_request(self):
        from concurrent.futures import ThreadPoolExecutor
        from github_access import GitHubMetadata
        import time

        def fetch(url, token):
            time.sleep(0.02)
            return {"ok": True}

        with tempfile.TemporaryDirectory() as directory:
            request = Mock(side_effect=fetch)
            cache = GitHubMetadata(directory, request)
            with ThreadPoolExecutor(max_workers=4) as workers:
                results = list(
                    workers.map(
                        lambda unused: cache.get("https://api.github.com/x"), range(4)
                    )
                )
            self.assertEqual(results, [{"ok": True}] * 4)
            self.assertEqual(request.call_count, 1)

    def test_rate_limit_honors_reset_without_retries_and_new_token_can_proceed(self):
        import urllib.error
        from github_access import GitHubMetadata

        headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "5000"}
        blocked = urllib.error.HTTPError(
            "https://api.github.com/x", 403, "limited", headers, None
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("github_access.time.time", return_value=1000),
            patch.dict("os.environ", {}, clear=True),
        ):
            fetch = Mock(side_effect=[blocked, {"ok": True}])
            cache = GitHubMetadata(directory, fetch)
            with self.assertRaisesRegex(RuntimeError, "paused until"):
                cache.get("https://api.github.com/x")
            with self.assertRaisesRegex(RuntimeError, "paused until"):
                cache.get("https://api.github.com/y", force=True)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(
                cache.blocked[__import__("hashlib").sha256(b"").hexdigest()], 5001
            )
            self.assertEqual(
                cache.get("https://api.github.com/y", "synthetic-token"), {"ok": True}
            )
            self.assertEqual(fetch.call_count, 2)
            for path in Path(directory).glob("*.json"):
                self.assertNotIn("synthetic-token", path.read_text())

    def test_retry_after_and_non_rate_errors(self):
        import urllib.error
        from github_access import GitHubMetadata

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("github_access.time.time", return_value=1000),
            patch.dict("os.environ", {}, clear=True),
        ):
            limited = urllib.error.HTTPError(
                "https://api.github.com/x", 429, "limited", {"Retry-After": "120"}, None
            )
            fetch = Mock(side_effect=limited)
            cache = GitHubMetadata(directory, fetch)
            with self.assertRaisesRegex(RuntimeError, "paused until"):
                cache.get("https://api.github.com/x")
            self.assertEqual(next(iter(cache.blocked.values())), 1120)
            denied = GitHubMetadata(directory, Mock(side_effect=OSError("offline")))
            with self.assertRaisesRegex(OSError, "offline"):
                denied.get("https://api.github.com/z")
            self.assertFalse(denied.blocked)

    def test_token_is_session_only_and_rejects_whitespace(self):
        service = desktop.DesktopServices(ROOT, ROOT)
        service.set_github_token("synthetic-token")
        self.assertEqual(service.github_token, "synthetic-token")
        with self.assertRaises(ValueError):
            service.set_github_token("invalid token")
        service.set_github_token("")
        self.assertEqual(service.github_token, "")


if __name__ == "__main__":
    unittest.main()
