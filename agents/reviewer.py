import logging

import audit
from agent import run_agent
from agents.base import BaseAgent
from prompts.review_prompt import build_review_prompt

_MAX_DIFF_CHARS = 40_000


class ReviewerAgent(BaseAgent):
    @property
    def default_interval(self) -> int:
        return 60

    async def run_once(self) -> None:
        projects = self.config.get("projects", [])
        branch_prefixes = tuple(p["branch_prefix"] for p in projects)
        configured_repos = {p["github_repo"] for p in projects}

        bot_login = await self.github.get_bot_login_async()

        for repo in configured_repos:
            prs = await self.github.get_open_prs_async(repo)
            for pr in prs:
                if pr["head_branch"].startswith(branch_prefixes):
                    logging.info(
                        f"[{self.agent_id}] Skipping self-authored PR #{pr['number']}: {pr['head_branch']}"
                    )
                    audit.log_event(
                        "pr_skipped",
                        agent_id=self.agent_id,
                        repo=repo,
                        pr_number=pr["number"],
                        reason="self_authored",
                    )
                    continue
                if await self.github.has_bot_reviewed_async(repo, pr["number"], bot_login):
                    logging.info(
                        f"[{self.agent_id}] Already reviewed PR #{pr['number']}, skipping"
                    )
                    audit.log_event(
                        "pr_skipped",
                        agent_id=self.agent_id,
                        repo=repo,
                        pr_number=pr["number"],
                        reason="already_reviewed",
                    )
                    continue
                logging.info(
                    f"[{self.agent_id}] Reviewing PR #{pr['number']}: {pr['title']}"
                )
                await self._review_pr(repo, pr["number"])

    async def _review_pr(self, repo: str, pr_number: int) -> None:
        meta = await self.github.get_pr_metadata_async(repo, pr_number)
        diff = (await self.github.get_pr_diff_async(repo, pr_number))[:_MAX_DIFF_CHARS]
        repo_summary = await self.github.get_repo_summary_async(repo)
        prompt = build_review_prompt(meta, diff, repo_summary)
        result = await run_agent(repo_path=None, prompt=prompt)
        if result.success and result.summary:
            await self.github.post_pr_review_async(repo, pr_number, body=result.summary)
            audit.log_event(
                "pr_review_posted",
                agent_id=self.agent_id,
                repo=repo,
                pr_number=pr_number,
                pr_title=meta["title"],
            )
            logging.info(
                f"[{self.agent_id}] Posted review on PR #{pr_number} in {repo}"
            )
        else:
            audit.log_event(
                "pr_review_failed",
                agent_id=self.agent_id,
                repo=repo,
                pr_number=pr_number,
                error=result.error,
            )
            logging.warning(
                f"[{self.agent_id}] Agent failed for PR #{pr_number}: {result.error}"
            )
