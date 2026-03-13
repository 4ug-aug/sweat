"""Convenience entry point — runs the first configured implementer agent once."""
import asyncio
import sys

import config
from agents.implementer import ImplementerAgent
from clients.asana import AsanaClient
from clients.github import GitHubClient
from exceptions import SweatError


def _build_implementer(dry_run: bool = False) -> ImplementerAgent:
    github = GitHubClient(config.GITHUB_TOKEN)
    asana = AsanaClient(config.ASANA_TOKEN)
    agent_cfg = next(a for a in config.AGENTS if a["type"] == "implementer")
    return ImplementerAgent(
        agent_id=agent_cfg["id"],
        config=agent_cfg,
        github=github,
        asana=asana,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    try:
        asyncio.run(_build_implementer(dry_run).run_once())
    except SweatError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
