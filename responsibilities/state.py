from __future__ import annotations
import json
import os
from typing import Protocol


class ResponsibilityStateBackend(Protocol):
    def is_handled(self, event_key: str) -> bool: ...
    def mark_handled(self, event_key: str, metadata: dict | None = None) -> None: ...
    def get_revision_count(self, pr_key: str) -> int: ...
    def increment_revision_count(self, pr_key: str) -> None: ...
    def cleanup(self, open_pr_keys: set[str]) -> None: ...


class JsonFileState:
    """File-backed state for responsibility tracking."""

    def __init__(self, path: str | None = None):
        if path is None:
            import config
            path = config.RESPONSIBILITIES_STATE_PATH
        self._path = path

    def _load(self) -> dict:
        if not os.path.exists(self._path):
            return {"handled": {}, "revision_counts": {}}
        with open(self._path) as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)

    def is_handled(self, event_key: str) -> bool:
        return event_key in self._load()["handled"]

    def mark_handled(self, event_key: str, metadata: dict | None = None) -> None:
        from datetime import datetime, timezone
        data = self._load()
        data["handled"][event_key] = {
            "handled_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self._save(data)

    def get_revision_count(self, pr_key: str) -> int:
        return self._load()["revision_counts"].get(pr_key, 0)

    def increment_revision_count(self, pr_key: str) -> None:
        data = self._load()
        data["revision_counts"][pr_key] = data["revision_counts"].get(pr_key, 0) + 1
        self._save(data)

    def cleanup(self, open_pr_keys: set[str]) -> None:
        """Remove entries for PRs no longer open."""
        data = self._load()
        # Remove revision_counts for closed PRs
        data["revision_counts"] = {
            k: v for k, v in data["revision_counts"].items()
            if k in open_pr_keys
        }
        # Remove handled events for closed PRs
        # event_key format: "{repo}#{pr_number}:..." so pr_key is "{repo}#PR{pr_number}"
        # We need to match event keys to pr keys
        def event_belongs_to_open_pr(event_key: str) -> bool:
            # event_key format examples:
            # "org/repo#42:review:98765" -> pr_key "org/repo#PR42"
            # "org/repo#42:ci_failure" -> pr_key "org/repo#PR42"
            # "org/repo#42:comment:12345" -> pr_key "org/repo#PR42"
            parts = event_key.split(":")
            if len(parts) >= 2:
                # parts[0] is "org/repo#42"
                repo_pr = parts[0]
                if "#" in repo_pr:
                    repo, pr_num = repo_pr.rsplit("#", 1)
                    pr_key = f"{repo}#PR{pr_num}"
                    return pr_key in open_pr_keys
            return True  # keep if can't parse

        data["handled"] = {
            k: v for k, v in data["handled"].items()
            if event_belongs_to_open_pr(k)
        }
        self._save(data)
