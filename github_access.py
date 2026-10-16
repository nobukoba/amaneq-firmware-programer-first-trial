"""Cached, serialized GitHub metadata reads with rate-limit backoff."""

import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import uuid
from datetime import datetime, timezone


class GitHubMetadata:
    def __init__(self, directory, fetch):
        self.directory = Path(directory)
        self.fetch = fetch
        self.lock = threading.RLock()
        self.blocked = {}

    def get(self, url, token="", force=False):
        token = token or os.environ.get("GITHUB_TOKEN", "")
        identity = hashlib.sha256(token.encode()).hexdigest()
        key = hashlib.sha256((identity + ":" + url).encode()).hexdigest()
        cache = self.directory / (key + ".json")
        immutable = bool(re.search(r"/(?:git/trees|commits)/[0-9a-f]{40}(?:\?|$)", url))
        with self.lock:
            now = time.time()
            try:
                saved = json.loads(cache.read_text(encoding="utf-8"))
                age = now - float(saved["timestamp"])
                if 0 <= age < (86400 if immutable else 300) and (
                    immutable or not force
                ):
                    return saved["data"]
            except (OSError, ValueError, KeyError, TypeError):
                pass
            if self.blocked.get(identity, 0) > now:
                self.raise_paused(self.blocked[identity])
            try:
                result = self.fetch(url, token)
            except Exception as error:
                cause = error
                while cause.__cause__ is not None:
                    cause = cause.__cause__
                if isinstance(cause, urllib.error.HTTPError) and cause.code in (
                    403,
                    429,
                ):
                    deadline = now + 60
                    try:
                        deadline = max(
                            deadline, now + float(cause.headers.get("Retry-After", "0"))
                        )
                        if cause.headers.get("X-RateLimit-Remaining") == "0":
                            deadline = max(
                                deadline,
                                float(cause.headers.get("X-RateLimit-Reset", "0")) + 1,
                            )
                    except (TypeError, ValueError, AttributeError):
                        pass
                    self.blocked[identity] = deadline
                    self.raise_paused(deadline, error)
                raise
            try:
                self.directory.mkdir(parents=True, exist_ok=True)
                temporary = cache.with_name(
                    cache.name + "." + uuid.uuid4().hex + ".tmp"
                )
                temporary.write_text(
                    json.dumps({"timestamp": now, "data": result}), encoding="utf-8"
                )
                temporary.replace(cache)
            except OSError:
                pass
            return result

    @staticmethod
    def raise_paused(deadline, cause=None):
        resume = datetime.fromtimestamp(deadline, timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        raise RuntimeError(
            f"GitHub API access paused until {resume} after HTTP 403/429. "
            "No request was retried. Wait until this time, or download an image "
            "from the repository in your browser and choose Local file."
        ) from cause
