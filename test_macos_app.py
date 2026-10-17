import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parent / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


app = load("desktop_app", "amaneq-firmware-app.py")
builder = load("macos_builder", "build-macos-app.py")


class MacBundleTests(unittest.TestCase):
    def test_macos_data_is_outside_app(self):
        with (
            patch.object(app.sys, "platform", "darwin"),
            patch.object(app.Path, "home", return_value=Path("/Users/example")),
        ):
            self.assertEqual(
                app.app_data_directory().as_posix(),
                "/Users/example/Library/Application Support/AMANEQ",
            )

    def test_bundled_loader_preferred_without_homebrew(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(app, "ROOT", Path(tmp)),
            patch.object(app.sys, "platform", "darwin"),
        ):
            loader = Path(tmp) / "runtime/macos/bin/openFPGALoader"
            loader.parent.mkdir(parents=True)
            loader.write_bytes(b"fixture")
            self.assertEqual(Path(app.default_loader()), loader)

    def test_dependency_audit_rejects_homebrew(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "binary").write_bytes(b"\xcf\xfa\xed\xfe")
            with patch.object(
                builder,
                "capture",
                return_value="binary:\n /opt/homebrew/opt/libusb/lib/libusb.dylib (compatibility version 1)",
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "External runtime dependency"
                ):
                    builder.audit_dependencies(folder)
            with patch.object(
                builder,
                "capture",
                return_value="binary:\n @rpath/libusb.dylib (compatibility version 1)\n /usr/lib/libSystem.B.dylib (compatibility version 1)",
            ):
                builder.audit_dependencies(folder)

    def test_source_checksum_failure_never_saves_archive(self):
        import io

        info = {
            "name": "fixture",
            "urls": {
                "stable": {
                    "url": "https://example.invalid/source.tar",
                    "checksum": "0" * 64,
                }
            },
        }
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(
                builder.urllib.request, "urlopen", return_value=io.BytesIO(b"corrupt")
            ),
        ):
            destination = Path(tmp) / "source.tar"
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                builder.fetch_source(info, destination)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()


class NotarizationTests(unittest.TestCase):
    def test_signing_order_signs_macho_before_containing_bundles(self):
        signer = load("macos_notarizer", "macos_notarization.py")
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "Example.app"
            framework = bundle / "Contents/Frameworks/Python.framework"
            framework.mkdir(parents=True)
            binary = framework / "Python"
            binary.write_bytes(bytes.fromhex("feedfacf") + b"fixture")
            (bundle / "notes.txt").write_text("not executable", encoding="utf-8")
            self.assertEqual(signer.signing_order(bundle), [binary, framework, bundle])

    def exercise_submission(self, status):
        import json
        from types import SimpleNamespace

        signer = load("macos_notarizer", "macos_notarization.py")
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "Example.app"
            bundle.mkdir()
            output = Path(tmp) / "output"
            calls = []

            def fake_run(*args, capture=False):
                calls.append(args)
                if args[0] == "ditto":
                    Path(args[-1]).write_bytes(b"synthetic archive")
                if args[:3] == ("xcrun", "notarytool", "submit"):
                    return json.dumps({"id": "11111111-2222-3333-4444-555555555555"})
                if args[:3] in (
                    ("xcrun", "notarytool", "info"),
                    ("xcrun", "notarytool", "wait"),
                ):
                    return json.dumps({"status": status})
                if args[:2] == ("uname", "-m"):
                    return "arm64\n"
                return ""

            signature = SimpleNamespace(
                stderr=(
                    "Authority=Developer ID Application: Example\n"
                    "TeamIdentifier=ABCDE12345\n"
                )
            )
            with (
                patch.object(signer.sys, "platform", "darwin"),
                patch.object(signer, "run", side_effect=fake_run),
                patch.object(signer.subprocess, "run", return_value=signature),
            ):
                if status == "Accepted":
                    signer.notarize(
                        bundle,
                        "Developer ID Application: Example",
                        "test-profile",
                        output,
                        Path(tmp) / "test.keychain",
                    )
                else:
                    with self.assertRaises(RuntimeError):
                        signer.notarize(
                            bundle,
                            "Developer ID Application: Example",
                            "test-profile",
                            output,
                        )
            archives = list(output.glob("*-notarized.zip"))
            if status == "Accepted":
                self.assertEqual(len(archives), 1)
                self.assertIn(("xcrun", "stapler", "validate", bundle.resolve()), calls)
                self.assertIn(
                    (
                        "spctl",
                        "--assess",
                        "--type",
                        "execute",
                        "--verbose=4",
                        bundle.resolve(),
                    ),
                    calls,
                )
                submission = next(
                    call
                    for call in calls
                    if call[:3] == ("xcrun", "notarytool", "submit")
                )
                self.assertIn("--keychain", submission)
            else:
                self.assertFalse(archives)
                self.assertFalse(
                    any(call[:2] == ("xcrun", "stapler") for call in calls)
                )

    def test_only_accepted_submission_is_stapled_and_packaged(self):
        self.exercise_submission("Accepted")

    def test_rejected_submission_never_produces_a_notarized_archive(self):
        self.exercise_submission("Invalid")

    def test_adhoc_identity_is_rejected_before_any_commands(self):
        signer = load("macos_notarizer", "macos_notarization.py")
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "Example.app"
            bundle.mkdir()
            with (
                patch.object(signer.sys, "platform", "darwin"),
                patch.object(signer, "run") as command,
            ):
                with self.assertRaises(ValueError):
                    signer.notarize(bundle, "-", "profile", Path(tmp) / "output")
                command.assert_not_called()


class NotaryWaitRecoveryTests(unittest.TestCase):
    def test_timeout_keeps_id_archive_and_resumes_without_resubmission(self):
        import hashlib
        import json
        import subprocess

        signer = load("macos_notarizer", "macos_notarization.py")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            archive = folder / "submission.zip"
            archive.write_bytes(b"exact signed submission")
            submission_id = "11111111-2222-3333-4444-555555555555"

            def pending_run(*args, capture=False):
                if args[:3] == ("xcrun", "notarytool", "submit"):
                    self.assertNotIn("--wait", args)
                    return json.dumps({"id": submission_id})
                if args[:3] == ("xcrun", "notarytool", "wait"):
                    raise subprocess.CalledProcessError(
                        124,
                        "notarytool",
                        output="timeout output",
                        stderr="wait timed out",
                    )
                return json.dumps({"id": submission_id, "status": "In Progress"})

            with patch.object(signer, "run", side_effect=pending_run):
                with self.assertRaisesRegex(RuntimeError, "still pending"):
                    signer.complete_submission(
                        archive, "profile", None, folder, "90m", False
                    )
            state = json.loads((folder / "notary-submission.json").read_text())
            self.assertEqual(state["id"], submission_id)
            self.assertEqual(
                state["sha256"], hashlib.sha256(archive.read_bytes()).hexdigest()
            )
            self.assertEqual(
                json.loads((folder / "notary-result.json").read_text())["status"],
                "In Progress",
            )
            self.assertTrue((folder / "notary-wait.stderr.txt").is_file())

            with patch.object(
                signer,
                "run",
                return_value=json.dumps({"id": submission_id, "status": "Accepted"}),
            ) as command:
                signer.complete_submission(
                    archive, "profile", None, folder, "90m", True
                )
            self.assertFalse(
                any(
                    call.args[:3]
                    in (
                        ("xcrun", "notarytool", "submit"),
                        ("xcrun", "notarytool", "wait"),
                    )
                    for call in command.call_args_list
                )
            )
            self.assertTrue(archive.is_file())

    def test_resume_rejects_modified_archive_before_service_access(self):
        import json

        signer = load("macos_notarizer", "macos_notarization.py")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            archive = folder / "submission.zip"
            archive.write_bytes(b"modified")
            (folder / "notary-submission.json").write_text(
                json.dumps(
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "sha256": "0" * 64,
                    }
                )
            )
            with patch.object(signer, "run") as command:
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    signer.complete_submission(
                        archive, "profile", None, folder, "90m", True
                    )
                command.assert_not_called()
