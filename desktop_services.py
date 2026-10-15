"""Read-only cable discovery and cached latest-image catalog for the desktop UI."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import time


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


class DesktopServices:
    def __init__(self, root, data_root):
        self.data_root = data_root
        self.core = load_core(root, data_root)

    def scan(self, loader):
        return self.core.scan_cables(argparse.Namespace(loader=loader, cable="auto"))

    def catalog(self, force=False):
        cache = self.data_root / "latest-images.json"
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

    def _repository_rows(self, family, repository):
        github = self.core.GitHub(repository)
        branch = github.get("")["default_branch"]
        commit = github.revision(branch)
        entries = github.files(commit)
        result = []
        targets = (
            ["hrtdc-mezzanine"] if family == "mezzanine" else ["amaneq-v1", "amaneq-v4"]
        )
        firmware = "hrtdc" if family == "mezzanine" else family
        for target in targets:
            for format in (["mcs", "bit"] if firmware == "skeleton" else ["mcs"]):
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
