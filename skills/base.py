from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SkillContext:
    task: dict
    repo: str
    repo_path: str
    agent_id: str


class BaseSkill(ABC):
    name: str
    description: str

    @abstractmethod
    def build_prompt_fragment(self, context: SkillContext) -> str:
        """Return a prompt fragment injected into the agent prompt."""

    async def setup(self, context: SkillContext) -> None:
        """Optional: run before the Claude Code SDK session starts."""

    async def teardown(self, context: SkillContext) -> None:
        """Optional: run after the session ends."""
