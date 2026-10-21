"""Publish verified main-branch desktop artifacts with stable public URLs."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.request

SPECS = {
    "desktop": (
        "desktop-app.yml", "desktop-preview", "Windows and Linux preview",
        {"amaneq-firmware-programer-windows-x64": "amaneq-firmware-programer-windows-x64.zip",
         "amaneq-firmware-programer-linux-x86_64": "amaneq-firmware-programer-linux-x86_64.tar.gz"},
    ),
    "macos": (
        "macos-app.yml", "macos-preview", "macOS preview (not notarized)",
        {"amaneq-firmware-programer-macos-arm64": "amaneq-firmware-programer-macos-arm64.zip",
         "amaneq-firmware-programer-macos-x86_64": "amaneq-firmware-programer-macos-x86_64.zip"},
    ),
}


def api(repository, path, data=None, method=None):
    token = os.environ["GH_TOKEN"]
    request = urllib.request.Request(
        "https://api.github.com/repos/" + repository + "/" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404 and data is None:
            return None
        raise


def trusted_run(run, repository, workflow):
    return bool(
        run and run.get("conclusion") == "success" and run.get("status") == "completed"
        and run.get("head_branch") == "main"
        and run.get("head_repository", {}).get("full_name") == repository
        and run.get("event") in ("push", "workflow_dispatch")
        and run.get("path", "").split("@")[0] == ".github/workflows/" + workflow
        and re.fullmatch(r"[0-9a-f]{40}", run.get("head_sha", ""))
    )


def verify_files(folder, filename):
    archive = folder / filename
    checksum = folder / (filename + ".sha256")
    if archive.is_symlink() or checksum.is_symlink():
        raise ValueError("Symlink assets are not allowed.")
    fields = checksum.read_text(encoding="utf-8").split()
    if len(fields) != 2 or fields[1] != filename or not re.fullmatch(r"[0-9a-f]{64}", fields[0]):
        raise ValueError("Invalid SHA256 record for " + filename)
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != fields[0]:
        raise ValueError("SHA256 mismatch for " + filename)
    return [archive, checksum], {"sha256": fields[0], "size": archive.stat().st_size}


def publish(kind, repository, event):
    workflow, rolling, title, expected = SPECS[kind]
    if "workflow_run" in event:
        run = api(repository, "actions/runs/" + str(event["workflow_run"]["id"]))
        if not trusted_run(run, repository, workflow):
            return
    else:
        result = api(repository, "actions/workflows/" + workflow + "/runs?branch=main&status=success&per_page=30")
        run = next((r for r in result["workflow_runs"] if trusted_run(r, repository, workflow)), None)
        if not run:
            raise RuntimeError("No successful trusted build for " + kind)
    sha = run["head_sha"]
    ancestry = api(repository, "compare/" + sha + "...main")
    if not ancestry or ancestry["status"] not in ("ahead", "identical"):
        raise RuntimeError("Build commit is not on main.")
    existing = api(repository, "git/ref/tags/" + rolling)
    if existing:
        if existing["object"]["type"] != "commit":
            raise RuntimeError("Expected a lightweight rolling release tag.")
        comparison = api(repository, "compare/" + existing["object"]["sha"] + "..." + sha)
        if comparison["status"] == "behind":
            print("Keeping newer public download for " + kind)
            return
        if comparison["status"] not in ("ahead", "identical"):
            raise RuntimeError("Refusing a divergent rolling release update.")
    artifacts = api(repository, "actions/runs/" + str(run["id"]) + "/artifacts?per_page=100")["artifacts"]
    for name in expected:
        matching = [a for a in artifacts if a["name"] == name and not a["expired"]]
        if len(matching) != 1:
            raise RuntimeError("Missing or ambiguous build artifact: " + name)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        assets, records = [], {}
        for artifact, filename in expected.items():
            folder = root / artifact
            subprocess.run(["gh", "run", "download", str(run["id"]), "--repo", repository,
                            "--name", artifact, "--dir", str(folder)], check=True)
            files, record = verify_files(folder, filename)
            assets.extend(files)
            records[filename] = record
        version = rolling + "-" + sha[:12]
        manifest = root / "build-info.json"
        manifest.write_text(json.dumps({"commit": sha, "workflow_run": run["html_url"],
                                       "versioned_release": version, "files": records}, indent=2) + "\n")
        assets.append(manifest)
        notes = root / "notes.md"
        notes.write_text(
            f"{title}. Built and smoke-tested from `{sha}`.\n\n"
            f"Build: {run['html_url']}\n\n"
            "Download the archive for your OS under Assets. No GitHub account is required. "
            "SHA256 files and build-info.json identify the tested source and bytes. "
            "No hardware programming was performed by the build.\n"
        )
        for tag in (version, rolling):
            release = api(repository, "releases/tags/" + tag)
            if not release:
                api(repository, "releases", {"tag_name": tag, "target_commitish": sha,
                    "name": title + (" (latest successful build)" if tag == rolling else " " + sha[:12]),
                    "body": notes.read_text(), "prerelease": True, "make_latest": "false"})
            command = ["gh", "release", "upload", tag, "--repo", repository]
            if tag == rolling:
                command.append("--clobber")
            else:
                names = {a["name"] for a in (release or {}).get("assets", [])}
                missing = [a for a in assets if a.name not in names]
                if not missing:
                    continue
                subprocess.run(command + list(map(str, missing)), check=True)
                continue
            subprocess.run(command + list(map(str, assets)), check=True)
            if existing:
                api(repository, "git/refs/tags/" + rolling, {"sha": sha, "force": True}, "PATCH")
            updated = api(repository, "releases/tags/" + rolling)
            api(repository, "releases/" + str(updated["id"]), {"body": notes.read_text()}, "PATCH")
        print("Public download: https://github.com/" + repository + "/releases/tag/" + rolling)


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    repository = os.environ["GITHUB_REPOSITORY"]
    for kind in SPECS:
        publish(kind, repository, event)


if __name__ == "__main__":
    main()
