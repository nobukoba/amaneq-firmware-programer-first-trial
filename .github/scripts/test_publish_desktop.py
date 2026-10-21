"""Offline checks for privileged publication boundaries."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("publisher", Path(__file__).with_name("publish-desktop.py"))
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
REPO = "owner/repository"
SHA = "a" * 40


def build():
    return dict(id=1, conclusion="success", status="completed", head_branch="main",
                head_repository={"full_name": REPO}, event="push",
                path=".github/workflows/desktop-app.yml", head_sha=SHA)


class PublicationTests(unittest.TestCase):
    def test_reject_untrusted_builds(self):
        self.assertTrue(publisher.trusted_run(build(), REPO, "desktop-app.yml"))
        for field, value in [("conclusion", "failure"), ("status", "in_progress"),
                             ("head_branch", "feature"), ("event", "pull_request"),
                             ("head_repository", {"full_name": "fork/repo"}),
                             ("path", ".github/workflows/other.yml"), ("head_sha", "bad")]:
            run = build()
            run[field] = value
            with self.subTest(field=field):
                self.assertFalse(publisher.trusted_run(run, REPO, "desktop-app.yml"))

    def test_checksum_detects_changed_archive_and_wrong_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            archive = folder / "app.zip"
            archive.write_bytes(b"tested archive")
            checksum = folder / "app.zip.sha256"
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            checksum.write_text(digest + "  app.zip\n")
            self.assertEqual(publisher.verify_files(folder, "app.zip")[1]["sha256"], digest)
            archive.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                publisher.verify_files(folder, "app.zip")
            checksum.write_text(digest + "  another.zip\n")
            with self.assertRaisesRegex(ValueError, "Invalid"):
                publisher.verify_files(folder, "app.zip")

    def test_untrusted_event_never_downloads_or_writes(self):
        run = build()
        run["event"] = "pull_request"
        with patch.object(publisher, "api", return_value=run) as api, patch.object(publisher.subprocess, "run") as command:
            publisher.publish("desktop", REPO, {"workflow_run": {"id": 1}})
            self.assertEqual(api.call_count, 1)
            command.assert_not_called()

    def test_older_build_cannot_replace_newer_public_files(self):
        answers = [build(), {"status": "ahead"}, {"object": {"type": "commit", "sha": "b" * 40}}, {"status": "behind"}]
        with patch.object(publisher, "api", side_effect=answers) as api, patch.object(publisher.subprocess, "run") as command:
            publisher.publish("desktop", REPO, {"workflow_run": {"id": 1}})
            self.assertEqual(api.call_count, 4)
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
