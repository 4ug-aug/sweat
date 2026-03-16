from abc import ABC, abstractmethod

from clients.asana import AsanaClient
from clients.github import GitHubClient


class BaseAgent(ABC):
    def __init__(
        self,
        agent_id: str,
        config: dict,
        github: GitHubClient,
        asana: AsanaClient,
    ):
        self.agent_id = agent_id
        self.config = config
        self.github = github
        self.asana = asana

    @abstractmethod
    async def run_once(self) -> None:
        """Execute one cycle of this agent's work."""

    @property
    @abstractmethod
    def default_interval(self) -> int:
        """Default seconds between runs."""

    def get_loops(self) -> dict[str, int]:
        """Named loops with intervals. Default: just 'main' using default_interval."""
        return {"main": self.default_interval}

    async def run_loop(self, loop_name: str) -> None:
        """Dispatch to loop handler. Default: 'main' calls run_once()."""
        if loop_name == "main":
            await self.run_once()
