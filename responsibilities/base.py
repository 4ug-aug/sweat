from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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
    context: dict = field(default_factory=dict)  # responsibility-specific payload


class BaseResponsibility(ABC):
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
