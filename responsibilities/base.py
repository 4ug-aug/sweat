from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from clients.github import GitHubClient
    from clients.asana import AsanaClient
    from responsibilities.snapshot import PRSnapshot
    from responsibilities.state import ResponsibilityStateBackend


@dataclass
class ResponsibilityItem:
    kind: str           # "review_changes_requested", "ci_failure", "pr_comment"
    repo: str
    pr_number: int
    branch: str
    event_key: str      # unique key for dedup, e.g. "org/repo#42:review:98765"
    context: dict[str, Any] = field(default_factory=dict)


class BaseResponsibility(ABC):
    def __init__(self, max_revision_rounds: int = 3):
        self._max_revision_rounds = max_revision_rounds
        self._state: ResponsibilityStateBackend | None = None

    @abstractmethod
    async def check(
        self,
        snapshot: "PRSnapshot",
        state: "ResponsibilityStateBackend",
    ) -> list[ResponsibilityItem]:
        """Find responsibility items from the pre-fetched snapshot."""

    @abstractmethod
    async def execute(
        self,
        item: ResponsibilityItem,
        github: "GitHubClient",
        asana: "AsanaClient",
        agent_id: str,
    ) -> None:
        """Execute one responsibility item."""

    async def _check_revision_limit(
        self,
        item: ResponsibilityItem,
        github: "GitHubClient",
        agent_id: str,
        limit_message: str,
    ) -> bool:
        """Post a comment and return True if the PR has hit the revision limit."""
        assert self._state is not None, "check() must be called before execute()"
        pr_key = f"{item.repo}#PR{item.pr_number}"
        if self._state.get_revision_count(pr_key) >= self._max_revision_rounds:
            msg = (
                f"I've reached the maximum revision rounds ({self._max_revision_rounds}) for this PR. "
                f"{limit_message}"
            )
            await github.post_pr_comment_async(item.repo, item.pr_number, msg)
            logging.warning(f"[{agent_id}] Max revision rounds reached for {item.repo}#{item.pr_number}")
            return True
        return False
