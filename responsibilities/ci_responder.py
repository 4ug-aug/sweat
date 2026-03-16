from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import audit
from agents.helpers import work_on_branch
from prompts.ci_fix_prompt import build_ci_fix_prompt
from responsibilities.base import BaseResponsibility, ResponsibilityItem

if TYPE_CHECKING:
    from clients.asana import AsanaClient
    from clients.github import GitHubClient
    from responsibilities.snapshot import PRSnapshot
    from responsibilities.state import ResponsibilityStateBackend


class CIResponder(BaseResponsibility):
    def __init__(self, max_revision_rounds: int = 3):
        self._max_revision_rounds = max_revision_rounds
        self._state: "ResponsibilityStateBackend | None" = None

    async def check(
        self,
        snapshot: "PRSnapshot",
        state: "ResponsibilityStateBackend",
    ) -> list[ResponsibilityItem]:
        self._state = state
        items = []
        for pr in snapshot.prs:
            pr_number = pr["number"]
            repo = pr["repo"]
            branch = pr["head_branch"]
            status = snapshot.check_status.get(pr_number, "")
            if status not in ("failure", "error"):
                continue
            event_key = f"{repo}#{pr_number}:ci_failure"
            if state.is_handled(event_key):
                continue
            items.append(ResponsibilityItem(
                kind="ci_failure",
                repo=repo,
                pr_number=pr_number,
                branch=branch,
                event_key=event_key,
                context={},
            ))
        return items

    async def execute(
        self,
        item: ResponsibilityItem,
        github: "GitHubClient",
        asana: "AsanaClient",
        agent_id: str,
    ) -> None:
        assert self._state is not None, "check() must be called before execute()"
        state = self._state
        pr_key = f"{item.repo}#PR{item.pr_number}"

        if state.get_revision_count(pr_key) >= self._max_revision_rounds:
            msg = (
                f"I've reached the maximum revision rounds ({self._max_revision_rounds}) for this PR. "
                "Please investigate the CI failures manually."
            )
            await github.post_pr_comment_async(item.repo, item.pr_number, msg)
            logging.warning(f"[{agent_id}] Max revision rounds reached for {item.repo}#{item.pr_number}")
            return

        failed_checks = await github.get_failed_check_details_async(item.repo, item.pr_number)
        diff = await github.get_pr_diff_async(item.repo, item.pr_number)
        repo_summary = await github.get_repo_summary_async(item.repo)

        prompt = build_ci_fix_prompt(diff=diff, failed_checks=failed_checks, repo_summary=repo_summary)

        result = await work_on_branch(
            github=github,
            repo=item.repo,
            branch=item.branch,
            prompt=prompt,
            commit_message=f"fix: address CI failures on PR #{item.pr_number}",
        )

        if not result.success:
            error_msg = f"I encountered an error while trying to fix CI failures: {result.error}"
            await github.post_pr_comment_async(item.repo, item.pr_number, error_msg)
            logging.warning(f"[{agent_id}] Failed to fix CI for {item.repo}#{item.pr_number}: {result.error}")
            return

        await github.post_pr_comment_async(
            item.repo,
            item.pr_number,
            "Attempted CI fix — pushed to branch. Re-running checks.",
        )
        state.mark_handled(item.event_key)
        state.increment_revision_count(pr_key)
        audit.log_event(
            "ci_failure_addressed",
            agent_id=agent_id,
            repo=item.repo,
            pr_number=item.pr_number,
        )
        logging.info(f"[{agent_id}] Addressed CI failure on {item.repo}#{item.pr_number}")
