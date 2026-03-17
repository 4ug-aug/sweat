from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import audit
from agents.helpers import work_on_branch
from prompts.comment_response_prompt import build_comment_response_prompt
from responsibilities.base import BaseResponsibility, ResponsibilityItem

if TYPE_CHECKING:
    from clients.asana import AsanaClient
    from clients.github import GitHubClient
    from responsibilities.snapshot import PRSnapshot
    from responsibilities.state import ResponsibilityStateBackend


class CommentResponder(BaseResponsibility):
    async def check(
        self,
        snapshot: "PRSnapshot",
        state: "ResponsibilityStateBackend",
    ) -> list[ResponsibilityItem]:
        self._state = state
        bot_login = snapshot.bot_login
        items = []
        for pr in snapshot.prs:
            pr_number = pr["number"]
            repo = pr["repo"]
            branch = pr["head_branch"]
            threads = snapshot.comment_threads.get(pr_number, [])
            for thread in threads:
                root = thread.get("root", {})
                replies = thread.get("replies", [])
                # Find last comment in thread
                all_comments = [root] + replies
                if not all_comments:
                    continue
                last_comment = all_comments[-1]
                if last_comment.get("user_login") == bot_login:
                    continue  # last commenter is bot, nothing to do
                root_id = root.get("id")
                if root_id is None:
                    continue
                event_key = f"{repo}#{pr_number}:comment:{root_id}"
                if state.is_handled(event_key):
                    continue
                items.append(ResponsibilityItem(
                    kind="pr_comment",
                    repo=repo,
                    pr_number=pr_number,
                    branch=branch,
                    event_key=event_key,
                    context={
                        "thread": thread,
                        "root_comment_id": root_id,
                    },
                ))

            issue_comments = snapshot.issue_comments.get(pr_number, [])
            if issue_comments:
                last_issue_comment = issue_comments[-1]
                if last_issue_comment.get("user_login") != bot_login:
                    event_key = f"{repo}#{pr_number}:issue_comment:{last_issue_comment['id']}"
                    if not state.is_handled(event_key):
                        items.append(ResponsibilityItem(
                            kind="pr_issue_comment",
                            repo=repo,
                            pr_number=pr_number,
                            branch=branch,
                            event_key=event_key,
                            context={"comments": issue_comments},
                        ))
        return items

    async def execute(
        self,
        item: ResponsibilityItem,
        github: "GitHubClient",
        asana: "AsanaClient",
        agent_id: str,
    ) -> None:
        if await self._check_revision_limit(
            item, github, agent_id,
            "Please review the comments and take action manually.",
        ):
            return
        state = self._state
        pr_key = f"{item.repo}#PR{item.pr_number}"

        diff = await github.get_pr_diff_async(item.repo, item.pr_number)
        repo_summary = await github.get_repo_summary_async(item.repo)

        if item.kind == "pr_issue_comment":
            comments = item.context["comments"]
            threads_for_prompt = [{"root": c, "replies": []} for c in comments]
        else:
            threads_for_prompt = [item.context["thread"]]

        prompt = build_comment_response_prompt(
            comment_threads=threads_for_prompt,
            diff=diff,
            repo_summary=repo_summary,
        )

        result = await work_on_branch(
            github=github,
            repo=item.repo,
            branch=item.branch,
            prompt=prompt,
            commit_message=f"address PR comments on PR #{item.pr_number}",
        )

        if not result.success:
            error_msg = f"I encountered an error while addressing the comment: {result.error}"
            await github.post_pr_comment_async(item.repo, item.pr_number, error_msg)
            logging.warning(f"[{agent_id}] Failed to address comment on {item.repo}#{item.pr_number}: {result.error}")
            return

        summary = result.summary or ""
        if item.kind == "pr_issue_comment":
            reply_text = summary[len("REPLY:"):].strip() if summary.startswith("REPLY:") else summary or "Implemented the suggested changes."
            await github.post_pr_comment_async(item.repo, item.pr_number, reply_text)
        else:
            root_comment_id = item.context["root_comment_id"]
            if summary.startswith("REPLY:"):
                reply_text = summary[len("REPLY:"):].strip()
                await github.reply_to_pr_comment_async(item.repo, item.pr_number, root_comment_id, reply_text)
            else:
                await github.reply_to_pr_comment_async(
                    item.repo, item.pr_number, root_comment_id,
                    "Implemented the suggested changes."
                )

        state.mark_handled(item.event_key)
        state.increment_revision_count(pr_key)
        audit.log_event(
            "pr_comment_addressed",
            agent_id=agent_id,
            repo=item.repo,
            pr_number=item.pr_number,
        )
        logging.info(f"[{agent_id}] Addressed PR comment on {item.repo}#{item.pr_number}")
