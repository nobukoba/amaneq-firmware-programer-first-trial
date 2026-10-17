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
        "feedface", "cefaedfe", "feedfacf", "cffaedfe",
        "cafebabe", "bebafeca", "cafebabf", "bfbafeca",
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
            path for path in app.rglob("*")
            if path.is_dir() and not path.is_symlink()
            and path.suffix in (".framework", ".app", ".bundle", ".xpc")
        ),
        key=lambda path: (-len(path.parts), str(path)),
    )
    return files + bundles + [app]


def notarize(app, identity, profile, output, keychain=None):
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
    if output.exists():
        raise ValueError("Use a new output directory.")
    output.mkdir(parents=True)
    for path in signing_order(app):
        run(
            "codesign", "--force", "--timestamp", "--options", "runtime",
            "--sign", identity, path,
        )
    run("codesign", "--verify", "--deep", "--strict", app)
    signature = subprocess.run(
        ["codesign", "--display", "--verbose=4", str(app)],
        check=True, capture_output=True, text=True,
    ).stderr
    if "Authority=Developer ID Application:" not in signature:
        raise ValueError("The app is not signed with Developer ID Application.")
    if not re.search(r"^TeamIdentifier=[A-Z0-9]{10}$", signature, re.MULTILINE):
        raise ValueError("No valid Apple team identifier in signature.")
    submission = output / "submission.zip"
    run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, submission)
    keychain_arguments = ["--keychain", str(keychain)] if keychain else []
    response = json.loads(run(
        "xcrun", "notarytool", "submit", submission,
        "--keychain-profile", profile, "--wait", "--timeout", "30m",
        "--output-format", "json", *keychain_arguments, capture=True,
    ))
    (output / "notary-result.json").write_text(
        json.dumps(response, indent=2) + "\n", encoding="utf-8",
    )
    if response.get("status") != "Accepted":
        raise RuntimeError(
            "Apple did not accept the submission. Inspect the notary result/log "
            "before distributing; no notarized archive was produced."
        )
    run("xcrun", "stapler", "staple", app)
    run("xcrun", "stapler", "validate", app)
    run("codesign", "--verify", "--deep", "--strict", app)
    run("spctl", "--assess", "--type", "execute", "--verbose=4", app)
    architecture = run("uname", "-m", capture=True).strip()
    archive = output / f"amaneq-firmware-programer-macos-{architecture}-notarized.zip"
    run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, archive)
    (output / (archive.name + ".sha256")).write_text(
        hashlib.sha256(archive.read_bytes()).hexdigest()
        + "  " + archive.name + "\n", encoding="utf-8",
    )
    submission.unlink()
    print(archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path, help="App bundle to sign in place")
    parser.add_argument("--identity", required=True, help="Developer ID Application identity")
    parser.add_argument("--profile", required=True, help="Existing notarytool keychain profile")
    parser.add_argument("--keychain", type=Path, help="Keychain containing the notary profile")
    parser.add_argument("--output", type=Path, default=Path("dist/notarized"),
                        help="New output directory (default: dist/notarized)")
    args = parser.parse_args()
    try:
        notarize(args.app, args.identity, args.profile, args.output, args.keychain)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
