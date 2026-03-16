from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import audit
from agents.helpers import work_on_branch
from prompts.review_response_prompt import build_review_response_prompt
from responsibilities.base import BaseResponsibility, ResponsibilityItem

if TYPE_CHECKING:
    from clients.asana import AsanaClient
    from clients.github import GitHubClient
    from responsibilities.snapshot import PRSnapshot
    from responsibilities.state import ResponsibilityStateBackend


class ReviewResponder(BaseResponsibility):
    def __init__(self, max_revision_rounds: int = 3):
        self._max_revision_rounds = max_revision_rounds
        self._state: "ResponsibilityStateBackend | None" = None

    async def check(
        self,
        snapshot: "PRSnapshot",
        state: "ResponsibilityStateBackend",
    ) -> list[ResponsibilityItem]:
        self._state = state  # store for use in execute()
        items = []
        for pr in snapshot.prs:
            pr_number = pr["number"]
            repo = pr["repo"]
            branch = pr["head_branch"]
            for review in snapshot.reviews.get(pr_number, []):
                if review["state"] != "CHANGES_REQUESTED":
                    continue
                event_key = f"{repo}#{pr_number}:review:{review['id']}"
                if state.is_handled(event_key):
                    continue
                items.append(ResponsibilityItem(
                    kind="review_changes_requested",
                    repo=repo,
                    pr_number=pr_number,
                    branch=branch,
                    event_key=event_key,
                    context={
                        "review_id": review["id"],
                        "review_body": review["body"],
                    },
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
                "Please review and merge manually or provide more specific guidance."
            )
            await github.post_pr_comment_async(item.repo, item.pr_number, msg)
            logging.warning(f"[{agent_id}] Max revision rounds reached for {item.repo}#{item.pr_number}")
            return

        # Fetch context needed for the prompt
        meta = await github.get_pr_metadata_async(item.repo, item.pr_number)
        diff = await github.get_pr_diff_async(item.repo, item.pr_number)
        review_id = item.context["review_id"]
        inline_comments = await github.get_review_comments_async(item.repo, item.pr_number, review_id)

        prompt = build_review_response_prompt(
            pr_body=meta.get("body", ""),
            diff=diff,
            review_body=item.context["review_body"],
            inline_comments=inline_comments,
        )

        result = await work_on_branch(
            github=github,
            repo=item.repo,
            branch=item.branch,
            prompt=prompt,
            commit_message=f"address review feedback on PR #{item.pr_number}",
        )

        if not result.success:
            error_msg = f"I encountered an error while addressing the review feedback: {result.error}"
            await github.post_pr_comment_async(item.repo, item.pr_number, error_msg)
            logging.warning(f"[{agent_id}] Failed to address review on {item.repo}#{item.pr_number}: {result.error}")
            return

        await github.post_pr_comment_async(
            item.repo,
            item.pr_number,
            f"Addressed feedback from review #{review_id}.",
        )
        state.mark_handled(item.event_key)
        state.increment_revision_count(pr_key)
        audit.log_event(
            "review_feedback_addressed",
            agent_id=agent_id,
            repo=item.repo,
            pr_number=item.pr_number,
        )
        logging.info(f"[{agent_id}] Addressed review feedback on {item.repo}#{item.pr_number}")
