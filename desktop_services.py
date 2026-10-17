"""Read-only cable discovery and cached latest-image catalog for the desktop UI."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import time
import uuid
import threading
from github_access import GitHubMetadata


def load_core(root, data_root):
    path = root / "amaneq-firmware-programer.py"
    spec = importlib.util.spec_from_file_location("_amaneq_desktop_core", path)
    core = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = core
    sys.dont_write_bytecode = True
    spec.loader.exec_module(core)
    core.ROOT = data_root
    core.NETWORK_TIMEOUT = 12
    return core


class CategoryCooldown:
    """Pause catalog acquisition after four category changes per cycle."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.category = None
        self.changes = 0
        self.until = 0.0

    def remaining(self):
        import math

        seconds = max(0, math.ceil(self.until - self.clock()))
        if self.until and not seconds:
            self.until = 0.0
            self.changes = 0
        return seconds

    def observe(self, category):
        remaining = self.remaining()
        if self.category is None:
            self.category = category
        elif category != self.category:
            self.category = category
            if not remaining:
                self.changes += 1
                if self.changes >= 4:
                    self.until = self.clock() + 60
        return self.remaining()


class DesktopServices:
    def __init__(self, root, data_root):
        self.data_root = data_root
        self.core = load_core(root, data_root)
        self.github_token = ""
        self.request_state = threading.local()
        original_request = self.core.request_json

        def authenticated_request(url, token):
            self.core._DESKTOP_GITHUB_TOKEN = token
            return original_request(url)

        self.metadata = GitHubMetadata(
            data_root / "github-metadata", authenticated_request
        )
        self.core.request_json = lambda url: self.metadata.get(
            url, self.github_token, getattr(self.request_state, "force", False)
        )

    def set_github_token(self, token):
        token = token.strip()
        if any(character.isspace() for character in token):
            raise ValueError("The GitHub token must not contain whitespace.")
        self.github_token = token

    def local_profile(self, filename, board):
        target = self.core.filename_target(filename)
        family = self.core.filename_family(filename)
        if not target and family == "skeleton" and board == "AMANEQ":
            # The DAQ manual documents this image as shared by AMANEQ v1/v4.
            target = "amaneq-v4"
        if not target or not family:
            raise ValueError(
                "Cannot identify the local firmware target/family from its filename. "
                "Use an official firmware filename."
            )
        expected_board = "CIRASAME" if target == "cirasame" else "AMANEQ"
        if board != expected_board:
            raise ValueError(
                f"Local filename indicates {expected_board}; selected board is {board}."
            )
        return target, family

    def scan(self, loader):
        return self.core.scan_cables(argparse.Namespace(loader=loader, cable="auto"))

    def catalog(self, force=False):
        cache = self.data_root / "latest-images-v3.json"
        saved = None
        try:
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if (
                not isinstance(saved, dict)
                or saved.get("schema") != 1
                or not isinstance(saved.get("timestamp"), (int, float))
                or not isinstance(saved.get("rows"), list)
                or not isinstance(saved.get("checked_at"), str)
            ):
                saved = None
        except (OSError, ValueError):
            pass
        if saved and not force and time.time() - saved["timestamp"] < 300:
            return (
                saved["rows"],
                f"Cached latest list checked {saved['checked_at']}",
                [],
            )
        rows, errors = [], []
        repositories = [
            (name, "AMANEQ-official/" + repo)
            for name, repo in self.core.REPOS.items()
            if name != "skeleton"
        ]
        repositories.append(("skeleton", "spadi-alliance/AMANEQ-Skeleton"))
        repositories.extend(
            ("cirasame:" + family, "spadi-alliance/" + repo)
            for family, repo in self.core.CIRASAME_REPOS.items()
        )
        with ThreadPoolExecutor(max_workers=6) as executor:
            tasks = {
                executor.submit(self._repository_rows, family, repository): repository
                for family, repository in repositories
            }
            for future in as_completed(tasks):
                try:
                    rows.extend(future.result())
                except Exception as error:
                    errors.append(f"{tasks[future]}: {error}")
        checked = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if not rows:
            if saved:
                return (
                    saved["rows"],
                    f"Offline/cached list from {saved['checked_at']} (not refreshed)",
                    errors,
                )
            raise self.core.UserError(
                "Could not load latest firmware images. " + "; ".join(errors)
            )
        rows.sort(
            key=lambda row: (row["target"], row["firmware"], row["format"], row["path"])
        )
        if not errors:
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "timestamp": time.time(),
                        "checked_at": checked,
                        "rows": rows,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(cache)
        return (
            rows,
            f"Latest default-branch images checked {checked}"
            + (" (partial results)" if errors else ""),
            errors,
        )

    def default_repository(self, target, firmware):
        if target == "cirasame":
            return "spadi-alliance/" + self.core.CIRASAME_REPOS[firmware]
        if target == "hrtdc-mezzanine":
            return "AMANEQ-official/" + self.core.REPOS["mezzanine"]
        return (
            "spadi-alliance/" if firmware == "skeleton" else "AMANEQ-official/"
        ) + self.core.REPOS[firmware]

    def image_list(
        self,
        repository,
        target,
        firmware,
        force=False,
        include_history=False,
        history_limit=5,
        image_format=None,
    ):
        import hashlib

        self.request_state.force = force
        if isinstance(history_limit, bool) or not 1 <= int(history_limit) <= 1000:
            raise ValueError("History limit must be between 1 and 1000.")
        history_limit = int(history_limit)
        if image_format not in (None, "mcs", "bit"):
            raise ValueError("Image format must be MCS or BIT.")
        github = self.core.GitHub(repository.strip())
        key = hashlib.sha256(
            f"history-v9:{github.repo}:{target}:{firmware}:{include_history}:{history_limit}:{image_format}".encode()
        ).hexdigest()
        cache = self.data_root / "image-lists" / (key + ".json")
        saved = None
        try:
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if (
                not isinstance(saved.get("rows"), list)
                or not isinstance(saved.get("timestamp"), (float, int))
                or not isinstance(saved.get("checked_at"), str)
            ):
                saved = None
        except (OSError, ValueError, AttributeError):
            pass
        if saved and not force and time.time() - saved["timestamp"] < 300:
            return (
                saved["rows"],
                f"Cached firmware history checked {saved['checked_at']}",
                [],
            )
        try:
            branch = github.get("")["default_branch"]
            head = github.revision(branch)
            rows, errors, identities = [], [], set()
            formats = (
                [image_format]
                if image_format
                else (["mcs", "bit"] if firmware == "skeleton" else ["mcs"])
            )

            def add_snapshot(commit, revision, date="", current=False):
                entries = github.files(commit)
                for image_format in formats:
                    args = argparse.Namespace(
                        target=target,
                        firmware=firmware,
                        format=image_format,
                        flash="auto",
                    )
                    for item in self.core.candidates(entries, args):
                        family = self.core.filename_family(item["path"])
                        if family is not None and family != firmware:
                            continue
                        identity = (image_format, item["path"], item.get("sha", commit))
                        if identity in identities:
                            continue
                        identities.add(identity)
                        rows.append(
                            {
                                "target": target,
                                "firmware": firmware,
                                "format": image_format,
                                "repo": github.repo,
                                "commit": commit,
                                "path": item["path"],
                                "name": Path(item["path"]).name,
                                "revision": revision,
                                "date": date,
                                "is_current": current,
                            }
                        )

            add_snapshot(head, branch + " (current)", current=True)
            snapshots = 1
            if include_history and len(rows) < history_limit:
                import urllib.parse

                try:
                    scan_limit = min(1000, max(20, history_limit * 3))
                    tags = github.pages("/tags", scan_limit)
                    tag_names = {}
                    for tag in tags:
                        tag_names.setdefault(tag["commit"]["sha"], []).append(
                            tag["name"]
                        )
                    commits = {}
                    for directory in formats:
                        for item in github.pages(
                            "/commits?path=" + urllib.parse.quote(directory, safe=""),
                            scan_limit,
                        ):
                            commits[item["sha"]] = item
                    ordered = sorted(
                        commits.values(),
                        key=lambda item: item["commit"]["committer"]["date"],
                        reverse=True,
                    )
                    revisions = [
                        (item["sha"], item["commit"]["committer"]["date"])
                        for item in ordered
                    ]
                    revisions.extend(
                        (sha, "") for sha in tag_names if sha not in commits
                    )
                    seen = {head}
                    for commit, date in revisions:
                        if commit in seen:
                            continue
                        seen.add(commit)
                        if len(rows) >= history_limit:
                            break
                        revision = (
                            ", ".join(tag_names.get(commit, []))
                            or (date[:10] + " " + commit[:12]).strip()
                        )
                        add_snapshot(commit, revision, date)
                        snapshots += 1
                except Exception as error:
                    errors.append("History lookup incomplete: " + str(error))
            rows.sort(
                key=lambda row: (
                    row["is_current"],
                    self.core.version_key(row["path"]),
                    row["format"] == "mcs",
                    row["date"],
                    row["path"],
                ),
                reverse=True,
            )
            rows = rows[:history_limit]
            checked = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            if not errors:
                cache.parent.mkdir(parents=True, exist_ok=True)
                temporary = cache.with_name(
                    cache.name + "." + uuid.uuid4().hex + ".tmp"
                )
                temporary.write_text(
                    json.dumps(
                        {"rows": rows, "timestamp": time.time(), "checked_at": checked}
                    ),
                    encoding="utf-8",
                )
                temporary.replace(cache)
            scope = (
                "Default branch + tags/firmware commits"
                if include_history
                else "Default branch"
            )
            status = f"{scope}: {len(rows)} images, {snapshots} revisions checked {checked}; limit {history_limit}"
            if errors:
                status += " (history incomplete)"
            if not rows:
                status += ". No matching firmware images found."
            return rows, status, errors
        except Exception as error:
            if saved:
                return (
                    saved["rows"],
                    f"Offline/cached history from {saved['checked_at']} (not refreshed)",
                    [str(error)],
                )
            raise

    def _repository_rows(self, family, repository):
        github = self.core.GitHub(repository)
        branch = github.get("")["default_branch"]
        commit = github.revision(branch)
        entries = github.files(commit)
        result = []
        targets = (
            ["hrtdc-mezzanine"] if family == "mezzanine" else ["amaneq-v1", "amaneq-v4"]
        )
        if family.startswith("cirasame:"):
            targets = ["cirasame"]
            family = family.split(":", 1)[1]
        firmware = "hrtdc" if family == "mezzanine" else family
        for target in targets:
            for format in ("mcs", "bit"):
                args = argparse.Namespace(
                    target=target, firmware=firmware, format=format, flash="auto"
                )
                options = self.core.candidates(entries, args)
                if not options:
                    continue
                best = max(self.core.version_key(item["path"]) for item in options)
                for item in options:
                    if self.core.version_key(item["path"]) == best:
                        result.append(
                            {
                                "firmware": firmware,
                                "target": target,
                                "format": format,
                                "repo": repository,
                                "commit": commit,
                                "path": item["path"],
                                "name": Path(item["path"]).name,
                            }
                        )
        return result


def cable_arguments(serial, devices, confirmed_hs3):
    matches = [
        device for device in devices if device.get("serial") == serial and serial
    ]
    if len(matches) != 1:
        identifiers = (
            ", ".join(device.get("serial") or "<not reported>" for device in devices)
            or "none"
        )
        raise ValueError(
            "Select exactly one scanned cable serial. Candidates: " + identifiers
        )
    device = matches[0]
    if device.get("cable") == "xilinxPlatformCableUsb":
        return ["--cable", "xilinx", "--serial", serial]
    if (
        device.get("cable") == "digilent_hs3"
        or confirmed_hs3
        and device.get("vidpid", "").upper() == "0403:6014"
    ):
        return ["--cable", "hs3", "--serial", serial]
    raise ValueError(
        "The cable model is unknown. Confirm the physical HS3 model or use a supported cable."
    )
