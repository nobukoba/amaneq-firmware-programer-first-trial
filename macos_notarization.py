#!/usr/bin/env python3
"""Sign and notarize a macOS app using a local Developer ID and notary profile."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

MACHO_MAGICS = {
    bytes.fromhex(value)
    for value in (
        "feedface",
        "cefaedfe",
        "feedfacf",
        "cffaedfe",
        "cafebabe",
        "bebafeca",
        "cafebabf",
        "bfbafeca",
    )
}


def run(*arguments, capture=False):
    result = subprocess.run(
        [str(argument) for argument in arguments],
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return result.stdout if capture else ""


def is_macho(path):
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as source:
        return source.read(4) in MACHO_MAGICS


def signing_order(app):
    files = sorted(
        (path for path in app.rglob("*") if is_macho(path)),
        key=lambda path: (-len(path.parts), str(path)),
    )
    bundles = sorted(
        (
            path
            for path in app.rglob("*")
            if path.is_dir()
            and not path.is_symlink()
            and path.suffix in (".framework", ".app", ".bundle", ".xpc")
        ),
        key=lambda path: (-len(path.parts), str(path)),
    )
    return files + bundles + [app]


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def notary_json(action, arguments, credentials, output):
    try:
        raw = run(
            "xcrun",
            "notarytool",
            action,
            *arguments,
            *credentials,
            "--output-format",
            "json",
            capture=True,
        )
    except subprocess.CalledProcessError as error:
        (output / f"notary-{action}.stdout.txt").write_text(
            error.stdout or "",
            encoding="utf-8",
        )
        (output / f"notary-{action}.stderr.txt").write_text(
            error.stderr or "",
            encoding="utf-8",
        )
        raise
    response = json.loads(raw)
    if not isinstance(response, dict):
        raise ValueError(f"Unexpected notarytool {action} response.")
    return response


def complete_submission(submission, profile, keychain, output, wait_timeout, resume):
    credentials = ["--keychain-profile", profile]
    if keychain:
        credentials += ["--keychain", str(keychain)]
    state_path = output / "notary-submission.json"
    if resume:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("sha256") != hashlib.sha256(submission.read_bytes()).hexdigest():
            raise ValueError(
                "Saved submission archive checksum mismatch; refusing to resume."
            )
        submission_id = state.get("id", "")
    else:
        response = notary_json("submit", [submission], credentials, output)
        submission_id = response.get("id", "")
        save_json(
            state_path,
            {
                "id": submission_id,
                "sha256": hashlib.sha256(submission.read_bytes()).hexdigest(),
            },
        )
    if not re.fullmatch(
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", submission_id
    ):
        raise ValueError("No valid Apple submission ID was returned or saved.")
    print(f"Apple submission ID: {submission_id}", flush=True)
    result = notary_json("info", [submission_id], credentials, output)
    save_json(output / "notary-result.json", result)
    if result.get("status") not in ("Accepted", "Invalid", "Rejected"):
        try:
            result = notary_json(
                "wait",
                [submission_id, "--timeout", wait_timeout],
                credentials,
                output,
            )
        except subprocess.CalledProcessError as error:
            if error.returncode != 124:
                raise RuntimeError(
                    f"Apple wait failed (exit {error.returncode}). "
                    f"Submission {submission_id} is saved; inspect diagnostics before retrying."
                ) from None
            result = notary_json("info", [submission_id], credentials, output)
        save_json(output / "notary-result.json", result)
    status = result.get("status", "Unknown")
    print(f"Apple notarization status: {status}", flush=True)
    if status in ("Accepted", "Invalid", "Rejected"):
        try:
            log = run(
                "xcrun",
                "notarytool",
                "log",
                submission_id,
                *credentials,
                capture=True,
            )
            (output / "notary-log.json").write_text(log, encoding="utf-8")
        except subprocess.SubprocessError:
            print(
                "WARNING: Apple log retrieval failed; status is preserved.", flush=True
            )
    if status != "Accepted":
        if status in ("Invalid", "Rejected"):
            raise RuntimeError(
                f"Apple rejected submission {submission_id}. See notary-log.json; "
                "no notarized archive was produced."
            )
        raise RuntimeError(
            f"Apple submission {submission_id} is still pending ({status}). "
            "The wait expired; this is not a rejection. Resume this saved submission "
            "instead of uploading it again."
        )


def notarize(
    app, identity, profile, output, keychain=None, wait_timeout="90m", resume=False
):
    if not re.fullmatch(r"[1-9][0-9]{0,2}m", wait_timeout):
        raise ValueError("Wait timeout must be 1m..999m.")
    if sys.platform != "darwin":
        raise ValueError("Signing and notarization must run on macOS.")
    if app.is_symlink():
        raise ValueError("Choose the original .app bundle, not a symbolic link.")
    app = app.resolve()
    if not app.is_dir() or app.suffix != ".app":
        raise ValueError("Choose an existing standalone .app bundle.")
    if not identity.strip() or identity.strip() == "-":
        raise ValueError("A Developer ID Application identity is required.")
    if not profile.strip():
        raise ValueError("A notarytool keychain profile is required.")
    output = output.resolve()
    submission = output / "submission.zip"
    if resume:
        if not output.is_dir() or not submission.is_file():
            raise ValueError(
                "Resume requires saved submission.zip and notary-submission.json."
            )
        state = json.loads(
            (output / "notary-submission.json").read_text(encoding="utf-8")
        )
        if state.get("sha256") != hashlib.sha256(submission.read_bytes()).hexdigest():
            raise ValueError("Saved submission archive checksum mismatch.")
        restored = output / "resumed-app"
        if restored.exists():
            raise ValueError("Use a fresh extracted state directory for each resume.")
        restored.mkdir()
        run("ditto", "-x", "-k", submission, restored)
        app = restored / app.name
        if not app.is_dir():
            raise ValueError("Saved submission does not contain the expected app.")
    else:
        if output.exists():
            raise ValueError("Use a new output directory.")
        output.mkdir(parents=True)
        for path in signing_order(app):
            run(
                "codesign",
                "--force",
                "--timestamp",
                "--options",
                "runtime",
                "--sign",
                identity,
                path,
            )
        run("codesign", "--verify", "--deep", "--strict", app)
        signature = subprocess.run(
            ["codesign", "--display", "--verbose=4", str(app)],
            check=True,
            capture_output=True,
            text=True,
        ).stderr
        if "Authority=Developer ID Application:" not in signature:
            raise ValueError("The app is not signed with Developer ID Application.")
        if not re.search(r"^TeamIdentifier=[A-Z0-9]{10}$", signature, re.MULTILINE):
            raise ValueError("No valid Apple team identifier in signature.")
        run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, submission)
    complete_submission(submission, profile, keychain, output, wait_timeout, resume)
    run("xcrun", "stapler", "staple", app)
    run("xcrun", "stapler", "validate", app)
    run("codesign", "--verify", "--deep", "--strict", app)
    run("spctl", "--assess", "--type", "execute", "--verbose=4", app)
    architecture = run("uname", "-m", capture=True).strip()
    archive = output / f"amaneq-firmware-programer-macos-{architecture}-notarized.zip"
    run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, archive)
    (output / (archive.name + ".sha256")).write_text(
        hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n",
        encoding="utf-8",
    )
    (output / "validated-app-path.txt").write_text(str(app) + "\n", encoding="utf-8")
    print(archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path, help="App bundle to sign in place")
    parser.add_argument(
        "--identity", required=True, help="Developer ID Application identity"
    )
    parser.add_argument(
        "--profile", required=True, help="Existing notarytool keychain profile"
    )
    parser.add_argument(
        "--keychain", type=Path, help="Keychain containing the notary profile"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/notarized"),
        help="New output directory (default: dist/notarized)",
    )
    parser.add_argument(
        "--wait-timeout",
        default="90m",
        help="Apple result wait (default: 90m); timeout is not a rejection",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume the saved submission in --output without re-uploading",
    )
    args = parser.parse_args()
    try:
        notarize(
            args.app,
            args.identity,
            args.profile,
            args.output,
            args.keychain,
            args.wait_timeout,
            args.resume,
        )
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
