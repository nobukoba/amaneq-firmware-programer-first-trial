"""Offline checks for hosted signing credential setup; no real secrets or keychains."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class HostedSigningCredentialsTests(unittest.TestCase):
    def prepare(self, extra, fail=False):
        import base64
        import os
        from types import SimpleNamespace

        workflow = Path(__file__).with_name('.github') / 'workflows/macos-notarize.yml'
        script = workflow.read_text(encoding='utf-8').split("python3 - <<'PY'\n", 1)[1]
        script = '\n'.join(line[10:] for line in script.split('\n          PY', 1)[0].splitlines())
        calls = []

        def command(args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=1 if fail else 0)

        with tempfile.TemporaryDirectory() as tmp:
            environment = {
                'RUNNER_TEMP': tmp,
                'CERTIFICATE': base64.b64encode(b'synthetic certificate').decode(),
                'CERTIFICATE_PASSWORD': 'synthetic-password',
                'SIGNING_IDENTITY': 'synthetic-identity',
                **extra,
            }
            with (
                patch.dict(os.environ, environment, clear=True),
                patch('subprocess.run', side_effect=command),
                patch('subprocess.check_output', return_value='1) synthetic-identity'),
            ):
                exec(compile(script, str(workflow), 'exec'), {})
            self.assertFalse((Path(tmp) / 'amaneq-signing.p12').exists())
            self.assertFalse((Path(tmp) / 'amaneq-notary.p8').exists())
        return calls

    def test_account_authentication_and_cleanup(self):
        calls = self.prepare({
            'APPLE_ID': 'example@example.invalid',
            'APPLE_APP_SPECIFIC_PASSWORD': 'synthetic-app-password',
            'APPLE_TEAM_ID': 'ABCDE12345',
        })
        auth = next(args for args in calls if args[:3] == ('xcrun', 'notarytool', 'store-credentials'))
        self.assertIn('--apple-id', auth)
        self.assertIn('--team-id', auth)
        self.assertNotIn('--key', auth)

    def test_api_key_authentication_and_cleanup(self):
        calls = self.prepare({
            'API_KEY': 'synthetic-api-key', 'API_KEY_ID': 'synthetic-key-id',
            'API_ISSUER': 'synthetic-issuer',
        })
        auth = next(args for args in calls if args[:3] == ('xcrun', 'notarytool', 'store-credentials'))
        self.assertIn('--key', auth)
        self.assertIn('--issuer', auth)
        self.assertNotIn('--apple-id', auth)

    def test_partial_api_key_does_not_fall_back_to_account(self):
        with self.assertRaisesRegex(SystemExit, 'API_KEY_ID, API_ISSUER'):
            self.prepare({
                'API_KEY': 'synthetic-api-key', 'APPLE_ID': 'example@example.invalid',
                'APPLE_APP_SPECIFIC_PASSWORD': 'synthetic-app-password',
                'APPLE_TEAM_ID': 'ABCDE12345',
            })

    def test_missing_account_secrets_fail_before_keychain_creation(self):
        with patch('subprocess.run') as command:
            with self.assertRaisesRegex(SystemExit, 'Missing signing secrets'):
                self.prepare({})
            command.assert_not_called()

    def test_failure_does_not_expose_secret_arguments(self):
        with self.assertRaises(SystemExit) as error:
            self.prepare({
                'API_KEY': 'synthetic-api-key', 'API_KEY_ID': 'synthetic-key-id',
                'API_ISSUER': 'synthetic-issuer',
            }, fail=True)
        self.assertNotIn('synthetic-password', str(error.exception))
        self.assertIn('secret arguments are hidden', str(error.exception))


if __name__ == "__main__":
    unittest.main()
