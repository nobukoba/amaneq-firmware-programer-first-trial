import argparse
import contextlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import importlib.util
import sys

_spec = importlib.util.spec_from_file_location(
    "amaneq_firmware_programer",
    Path(__file__).with_name("amaneq-firmware-programer.py"),
)
app = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = app
_spec.loader.exec_module(app)

PAYLOAD = app.SYNC + struct.pack(">II", 0x30018001, 0x0364C093)


def record(address, kind, data=b""):
    body = bytes([len(data)]) + address.to_bytes(2, "big") + bytes([kind]) + data
    return ":" + (body + bytes([-sum(body) % 256])).hex().upper()


def mcs(payload=PAYLOAD):
    return (record(0, 0, payload) + "\n" + record(0, 1) + "\n").encode()


def bit(payload=PAYLOAD):
    header = b"\x00\x09\x0f\xf0\x0f\xf0\x0f\xf0\x0f\xf0\x00\x00\x01"
    for key, value in [
        ("a", b"test\0"),
        ("b", b"7k160tffg676\0"),
        ("c", b"2025/01/01\0"),
        ("d", b"00:00:00\0"),
    ]:
        header += key.encode() + len(value).to_bytes(2, "big") + value
    return header + b"e" + len(payload).to_bytes(4, "big") + payload


class ProgrammerTests(unittest.TestCase):
    def test_content_over_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wrong.bit"
            path.write_bytes(mcs())
            self.assertEqual(app.inspect_file(path).kind, "mcs")
            path = Path(tmp) / "wrong.mcs"
            path.write_bytes(bit())
            self.assertEqual(app.inspect_file(path).kind, "bit")

    def test_bit_mcs_payload_equivalence(self):
        with tempfile.TemporaryDirectory() as temporary:
            bit_path = Path(temporary) / "synthetic.bit"
            mcs_path = Path(temporary) / "synthetic.mcs"
            bit_path.write_bytes(bit())
            mcs_path.write_bytes(mcs())
            a = app.inspect_file(bit_path)
            b = app.inspect_file(mcs_path)
            self.assertEqual(a.payload, b.payload)
            self.assertEqual(a.idcode, 0x0364C093)

    def test_checksum_and_eof(self):
        with self.assertRaises(app.UserError):
            app.parse_mcs(mcs().replace(b"AA", b"AB", 1))
        with self.assertRaises(app.UserError):
            app.parse_mcs(record(0, 0, PAYLOAD).encode())

    def test_overlap_rejected(self):
        data = "\n".join(
            [record(0, 0, PAYLOAD), record(2, 0, b"abc"), record(0, 1)]
        ).encode()
        with self.assertRaises(app.UserError):
            app.parse_mcs(data)

    def test_bit_truncation_and_missing_id(self):
        with self.assertRaises(app.UserError):
            app.parse_bit(bit()[:-1])
        with self.assertRaises(app.UserError):
            app.config_idcode(app.SYNC + b"\x20\x00\x00\x00")

    def test_skeleton_common_v1_v4_and_repository(self):
        self.assertEqual(app.filename_family("amaneq-skeleton-v2.2.bit"), "skeleton")
        entries = [
            {"path": "bit/amaneq-skeleton-v2.2.bit"},
            {"path": "mcs/amaneq-skeleton-v2.2.mcs"},
        ]
        for target in ("amaneq-v1", "amaneq-v4"):
            args = argparse.Namespace(
                target=target,
                firmware="skeleton",
                repo=None,
                owner="AMANEQ-official",
                format="bit",
                flash="auto",
            )
            self.assertEqual(
                app.repository(args).repo, "spadi-alliance/AMANEQ-Skeleton"
            )
            self.assertEqual(app.candidates(entries, args), [entries[0]])
        args.target = "hrtdc-mezzanine"
        with self.assertRaises(app.UserError):
            app.repository(args)

    def test_bit_supported_for_all_families(self):
        image = app.Image("bit", PAYLOAD, {}, 0x0364C093)
        for family in ("skeleton", "lrtdc", "hrtdc", "lrtdc-10g", "mikumari"):
            app.validate_firmware_format(image, argparse.Namespace(firmware=family))
        with self.assertRaises(app.UserError):
            app.validate_firmware_format(
                app.Image("html", b"", {}, None), argparse.Namespace(firmware="lrtdc")
            )

    def test_new_firmware_families(self):
        self.assertEqual(
            app.filename_family("amaneq-4-strlrtdc-10g-v2.1.mcs"), "lrtdc-10g"
        )
        self.assertEqual(app.filename_family("amaneq-4-mch-v2.9.mcs"), "mikumari")
        self.assertEqual(
            app.repository(
                argparse.Namespace(
                    target="amaneq-v4",
                    firmware="lrtdc-10g",
                    repo=None,
                    owner="AMANEQ-official",
                )
            ).repo,
            "AMANEQ-official/StrLrTdc-10G",
        )
        self.assertEqual(
            app.repository(
                argparse.Namespace(
                    target="amaneq-v4",
                    firmware="mikumari",
                    repo=None,
                    owner="AMANEQ-official",
                )
            ).repo,
            "AMANEQ-official/MikuClockHub",
        )

    def test_version_hex_and_target(self):
        self.assertGreater(app.version_key("x-v2.A.bit"), app.version_key("x-v2.9.bit"))
        args = argparse.Namespace(
            format="mcs", target="amaneq-v4", flash="auto", firmware="lrtdc"
        )
        entries = [
            {"path": "mcs/amaneq-1-strlrtdc-v2.A.mcs"},
            {"path": "mcs/amaneq-4-strlrtdc-v2.A.mcs"},
        ]
        self.assertEqual(len(app.candidates(entries, args)), 1)

    def test_serial_selects_one(self):
        args = argparse.Namespace(serial="B", cable="auto", yes=True)
        devices = [
            {
                "serial": s,
                "cable": "digilent_hs3",
                "ready": True,
                "vidpid": "0403:6014",
                "busdev": "1:2",
            }
            for s in ("A", "B")
        ]
        with patch.object(app, "scan_cables", return_value=devices):
            device, selector = app.select_cable(args)
        self.assertEqual(device["serial"], "B")
        self.assertTrue("--ftdi-serial" in selector or "--busdev-num" in selector)

    def test_wizard_stops_before_prompts_for_multiple_cables(self):
        with (
            patch.object(
                app, "scan_cables", return_value=[{"serial": "A"}, {"serial": "B"}]
            ),
            patch.object(app, "choose") as choose,
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(app.UserError),
        ):
            app.main(["wizard"])
        choose.assert_not_called()

    def test_macos_scan_and_serial_selection(self):
        tree = [
            {
                "IORegistryEntryChildren": [
                    {
                        "idVendor": 0x0403,
                        "idProduct": 0x6014,
                        "USB Serial Number": "MAC-TEST",
                        "USB Product Name": "Digilent JTAG-HS3",
                    }
                ]
            }
        ]
        args = argparse.Namespace(cable="auto", serial=None, yes=True)
        with (
            patch.object(app.sys, "platform", "darwin"),
            patch.object(app, "loader_path", return_value="loader"),
            patch.object(
                app.subprocess,
                "run",
                side_effect=[
                    argparse.Namespace(stdout="digilent_hs3 supported"),
                    argparse.Namespace(stdout=app.plistlib.dumps(tree)),
                ],
            ),
        ):
            devices = app.scan_cables(args)
        self.assertEqual(devices[0]["serial"], "MAC-TEST")
        with (
            patch.object(app.sys, "platform", "darwin"),
            patch.object(app, "scan_cables", return_value=devices),
        ):
            self.assertEqual(
                app.select_cable(args)[1],
                ["-c", "digilent_hs3", "--ftdi-serial", "MAC-TEST"],
            )
            devices[0]["serial"] = ""
            with self.assertRaisesRegex(app.UserError, "serial number"):
                app.select_cable(args)

    def test_macos_invalid_usb_output(self):
        with (
            patch.object(app.sys, "platform", "darwin"),
            patch.object(app, "loader_path", return_value="loader"),
            patch.object(
                app.subprocess,
                "run",
                side_effect=[
                    argparse.Namespace(stdout="digilent_hs3 supported"),
                    argparse.Namespace(stdout=b"invalid"),
                ],
            ),
            self.assertRaisesRegex(app.UserError, "enumeration failed"),
        ):
            app.scan_cables(argparse.Namespace(cable="auto"))

    def test_multiple_cables_always_list_and_stop(self):
        for unattended in (True, False):
            args = argparse.Namespace(serial=None, cable="auto", yes=unattended)
            devices = [{"serial": "SERIAL_A"}, {"serial": "SERIAL_B"}]
            output = io.StringIO()
            with (
                patch.object(app, "scan_cables", return_value=devices),
                patch.object(app, "choose") as choose,
                contextlib.redirect_stderr(output),
                self.assertRaisesRegex(app.UserError, "--serial"),
            ):
                app.select_cable(args)
            choose.assert_not_called()
            self.assertIn("SERIAL_A", output.getvalue())
            self.assertIn("SERIAL_B", output.getvalue())

    def test_multiple_cables_stop_before_download(self):
        args = argparse.Namespace(serial=None, cable="auto", yes=False)
        with (
            patch.object(
                app, "scan_cables", return_value=[{"serial": "A"}, {"serial": "B"}]
            ),
            patch.object(app, "download") as download,
            patch.object(app, "choose") as choose,
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(app.UserError),
        ):
            app.program(args)
        download.assert_not_called()
        choose.assert_not_called()

    def test_unsupported_cable_stops(self):
        args = argparse.Namespace(serial=None, cable="auto", yes=True)
        device = {"serial": "X", "cable": None, "ready": False, "vidpid": "03FD:0008"}
        with (
            patch.object(app, "scan_cables", return_value=[device]),
            self.assertRaises(app.UserError),
        ):
            app.select_cable(args)

    def program_simulation(
        self, flash_model="spansion S25FL128S 256 sectors", wrong_readback=False
    ):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            path = tmp / "amaneq-4-strlrtdc-v2.A.mcs"
            path.write_bytes(mcs())
            args = argparse.Namespace(
                file=str(path),
                latest=False,
                choose_version=False,
                ref=None,
                target="amaneq-v4",
                firmware="lrtdc",
                yes=True,
                log_dir=str(tmp / "logs"),
                flash="auto",
            )
            operations = []

            def run(loader, arguments, env=None):
                operations.append(arguments)
                if "--detect" in arguments:
                    return "idcode 0x364c093\n"
                if "--dump-flash" in arguments:
                    count = int(arguments[arguments.index("--file-size") + 1])
                    dest = Path(arguments[-1])
                    dest.write_bytes(
                        (b"\0" * len(PAYLOAD) if wrong_readback else PAYLOAD)
                        if count == len(PAYLOAD)
                        else b"\xff" * count
                    )
                    return f"JEDEC ID: 0x012018\nDetected: {flash_model} size: 128Mb\n"
                return "Done\n"

            with (
                patch.object(
                    app,
                    "select_cable",
                    return_value=({"serial": "TEST"}, ["-c", "digilent_hs3"]),
                ),
                patch.object(app, "loader_path", return_value="loader"),
                patch.object(app, "environment", return_value={}),
                patch.object(app, "bridge_file", return_value=tmp / "bridge.bit"),
                patch.object(app, "run_loader", side_effect=run),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                try:
                    app.program(args)
                except app.UserError as error:
                    return operations, str(error)
            report = json.loads(next((tmp / "logs").glob("*result.json")).read_text())
            return operations, report["result"]

    def test_micron_flash_aliases(self):
        output = "JEDEC ID: 0x20bb19\nDetected: micron N25Q256A 512 sectors size: 256Mb"
        self.assertEqual(app.flash_identity(output)[0], "mt25qu256")
        with self.assertRaises(app.UserError):
            app.flash_identity(output.replace("256Mb", "128Mb"))

    def test_wrong_flash_never_erases(self):
        operations, result = self.program_simulation("micron MT25QU256")
        self.assertIn("Unexpected", result)
        self.assertFalse(any("-f" in operation for operation in operations))

    def test_flash_backup_write_verify_order(self):
        operations, result = self.program_simulation()
        self.assertIn("every byte verified", result)
        write = next(i for i, operation in enumerate(operations) if "-f" in operation)
        self.assertIn("--dump-flash", operations[write - 1])
        self.assertIn("--dump-flash", operations[write + 1])

    def test_readback_mismatch_is_failure(self):
        operations, result = self.program_simulation(wrong_readback=True)
        self.assertIn("readback mismatch", result)


class MezzanineAutoTests(unittest.TestCase):
    def probe(self, output):
        args = argparse.Namespace(firmware="hrtdc")
        device = {"serial": "TEST"}
        selector = ["-c", "digilent_hs3", "--ftdi-serial", "TEST"]
        with (
            patch.object(app, "select_cable", return_value=(device, selector)),
            patch.object(app, "loader_path", return_value="loader"),
            patch.object(app, "environment", return_value={}),
            patch.object(app, "bridge_file", return_value=Path("bridge.bit")),
            patch.object(
                app, "run_loader", side_effect=["idcode 0x364c093", output]
            ) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = app.detect_mezzanine_flash(args)
            self.assertTrue(
                all("-f" not in call.args[1] for call in run.call_args_list)
            )
            self.assertIn("--dump-flash", run.call_args_list[1].args[1])
            return result

    def test_detects_new_and_old_mezzanine(self):
        for identity, output in [
            (
                "mt25qu256",
                "JEDEC ID: 0x20bb19\nDetected: micron N25Q256A 512 sectors size: 256Mb",
            ),
            (
                "n25q128",
                "JEDEC ID: 0x20bb18\nDetected: micron MT25/N25Q128_1_8V 256 sectors size: 128Mb",
            ),
        ]:
            self.assertEqual(self.probe(output)[0], identity)

    def test_rejects_baseboard_flash(self):
        with self.assertRaisesRegex(app.UserError, "not a supported HR-TDC mezzanine"):
            self.probe(
                "JEDEC ID: 0x012018\nDetected: spansion S25FL128S 256 sectors size: 128Mb"
            )

    def test_detects_before_download(self):
        args = argparse.Namespace(
            file=None,
            url=None,
            latest=True,
            choose_version=False,
            ref=None,
            target="hrtdc-mezzanine",
            format="mcs",
            flash="auto",
        )
        downloaded = []

        def download(arguments):
            downloaded.append(arguments.flash)
            raise app.UserError("stop after download selection")

        with (
            patch.object(app, "select_cable", return_value=({"serial": "TEST"}, [])),
            patch.object(
                app,
                "detect_mezzanine_flash",
                return_value=("n25q128", ({"serial": "TEST"}, [])),
            ),
            patch.object(app, "download", side_effect=download),
            self.assertRaisesRegex(app.UserError, "stop after"),
        ):
            app.program(args)
        self.assertEqual(downloaded, ["n25q128"])

    def test_probe_failure_prevents_download(self):
        args = argparse.Namespace(
            file=None,
            url=None,
            latest=True,
            choose_version=False,
            ref=None,
            target="hrtdc-mezzanine",
            format="mcs",
            flash="auto",
        )
        with (
            patch.object(app, "select_cable", return_value=({"serial": "TEST"}, [])),
            patch.object(
                app, "detect_mezzanine_flash", side_effect=app.UserError("Unknown chip")
            ),
            patch.object(app, "download") as download,
            self.assertRaises(app.UserError),
        ):
            app.program(args)
        download.assert_not_called()


class HistoryLimitTests(unittest.TestCase):
    def commit(self, sha, date):
        return {
            "sha": sha,
            "commit": {"committer": {"date": date}, "message": "revision " + sha},
        }

    def test_total_limit_dedup_and_date_order(self):
        github = app.GitHub("example/repo")
        commits = [self.commit("new", "2025-03-01"), self.commit("old", "2025-01-01")]
        tag = {"name": "v1", "commit": {"sha": "old"}}
        with (
            patch.object(github, "get", return_value={"default_branch": "main"}),
            patch.object(github, "pages", side_effect=[commits, [tag]]),
        ):
            result = github.refs(3)
        self.assertEqual(len(result), 3)
        self.assertEqual([row[0] for row in result], ["main", "new", "v1"])

    def test_archived_tag_is_sorted_with_commits(self):
        github = app.GitHub("example/repo")
        commits = [self.commit("old", "2025-01-01")]
        tagged = self.commit("tagged", "2025-02-01")
        with (
            patch.object(
                github, "get", side_effect=[{"default_branch": "main"}, tagged]
            ),
            patch.object(
                github,
                "pages",
                side_effect=[commits, [{"name": "v2", "commit": {"sha": "tagged"}}]],
            ),
        ):
            self.assertEqual([row[0] for row in github.refs(2)], ["main", "v2"])

    def test_cli_default_and_override(self):
        with patch.object(app.GitHub, "refs", return_value=[]) as refs:
            app.main(["versions"])
            refs.assert_called_once_with(10)
        with patch.object(app.GitHub, "refs", return_value=[]) as refs:
            app.main(["versions", "--history-limit", "30"])
            refs.assert_called_once_with(30)


class NetworkTests(unittest.TestCase):
    def response(self, data, url="https://example.com/fw.bin", headers=None):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = data
        response.geturl.return_value = url
        response.headers = (
            headers if headers is not None else {"Content-Length": str(len(data))}
        )
        return response

    def test_dns_offline_message(self):
        error = app.urllib.error.URLError(app.socket.gaierror(-2, "offline"))
        with (
            patch.object(app.urllib.request, "urlopen", side_effect=error),
            self.assertRaisesRegex(app.UserError, "offline network"),
        ):
            app.fetch_bytes("https://example.com/fw.bit")

    def test_timeout_message(self):
        with (
            patch.object(app.urllib.request, "urlopen", side_effect=TimeoutError()),
            self.assertRaisesRegex(app.UserError, "timeout"),
        ):
            app.fetch_bytes("https://example.com/fw.bit")

    def test_http_404_and_no_query_leak(self):
        url = "https://example.com/fw.bit?token=SECRET"
        error = app.urllib.error.HTTPError(url, 404, "missing", {}, None)
        with patch.object(app.urllib.request, "urlopen", side_effect=error):
            try:
                app.fetch_bytes(url)
            except app.UserError as result:
                self.assertIn("HTTP 404", str(result))
                self.assertNotIn("SECRET", str(result))
            else:
                self.fail("Expected error")

    def test_tls_and_connection_errors(self):
        for error, expected in [
            (app.urllib.error.URLError(app.ssl.SSLError("certificate")), "TLS"),
            (app.urllib.error.URLError(ConnectionRefusedError()), "Connection failed"),
        ]:
            with (
                patch.object(app.urllib.request, "urlopen", side_effect=error),
                self.assertRaisesRegex(app.UserError, expected),
            ):
                app.fetch_bytes("https://example.com/fw.bit")

    def test_incomplete_and_size_limit(self):
        for response in [
            self.response(b"a", headers={"Content-Length": "10"}),
            self.response(b"abcd", headers={}),
        ]:
            with (
                patch.object(app.urllib.request, "urlopen", return_value=response),
                self.assertRaises(app.UserError),
            ):
                app.fetch_bytes("https://example.com/fw.bit", limit=3)

    def test_invalid_json(self):
        with (
            patch.object(
                app, "fetch_bytes", return_value=b"<html>offline proxy</html>"
            ),
            self.assertRaisesRegex(app.UserError, "JSON"),
        ):
            app.request_json("https://api.github.com/repos/a/b")

    def test_url_scheme_rejected_before_request(self):
        with (
            patch.object(app.urllib.request, "urlopen") as request,
            self.assertRaises(app.UserError),
        ):
            app.fetch_bytes("file:///firmware.bit")
        request.assert_not_called()

    def test_direct_url_content_not_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                url="https://example.com/firmware.mcs",
                sha256=None,
                download_dir=tmp,
                target="amaneq-v4",
                firmware="skeleton",
            )
            with (
                patch.object(app, "fetch_bytes", return_value=bit()),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                destination = app.download_url(args)
            self.assertEqual(destination.suffix, ".bit")
            self.assertEqual(app.inspect_file(destination).kind, "bit")

    def test_direct_html_and_hash_failure_leave_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                url="https://example.com/firmware.bit",
                sha256=None,
                download_dir=tmp,
                target="amaneq-v4",
                firmware="lrtdc",
            )
            with (
                patch.object(app, "fetch_bytes", return_value=b"<html>login</html>"),
                self.assertRaisesRegex(app.UserError, "direct file URL"),
            ):
                app.download_url(args)
            self.assertFalse(list(Path(tmp).rglob("*.tmp")))
            self.assertFalse(list(Path(tmp).rglob("*.bit")))
            args.sha256 = "0" * 64
            with (
                patch.object(app, "fetch_bytes", return_value=bit()),
                self.assertRaisesRegex(app.UserError, "SHA256"),
            ):
                app.download_url(args)

    def test_url_conflicting_options_and_timeout(self):
        with self.assertRaises(app.UserError):
            app.main(["download", "--url", "https://example.com/file.bit", "--latest"])
        with self.assertRaises(app.UserError):
            app.main(["download", "--timeout", "0"])


if __name__ == "__main__":
    unittest.main()
