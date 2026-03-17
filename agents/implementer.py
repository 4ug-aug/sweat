import logging
import math
import re
import shutil
import time
from datetime import date

import audit
from agent import AgentResult, run_agent
from agents.base import BaseAgent
from exceptions import AgentError
from prompts.task_prompt import build_agent_prompt
from task_claims import TaskClaims
from task_filter import filter_and_rank_tasks
from task_selector import select_task


def _branch_name(task: dict, prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", task["name"].lower()).strip("-")[:40]
    return f"{prefix}asana-{task['gid']}-{slug}"


class ImplementerAgent(BaseAgent):
    def __init__(self, *, dry_run: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.dry_run = dry_run
        # Late imports to avoid circular dependency:
        # agents.implementer -> responsibilities.registry -> responsibilities.review_responder -> agents.helpers
        from responsibilities.claims import ResponsibilityClaims
        from responsibilities.registry import RESPONSIBILITY_TYPES
        from responsibilities.state import JsonFileState
        self._state = JsonFileState()
        self._resp_claims = ResponsibilityClaims.get()
        responsibility_names = self.config.get("responsibilities", ["review_responder", "ci_responder", "comment_responder"])
        self._responsibilities = [
            RESPONSIBILITY_TYPES[name]()
            for name in responsibility_names
            if name in RESPONSIBILITY_TYPES
        ]

    @property
    def default_interval(self) -> int:
        return 3600

    def get_loops(self) -> dict[str, int]:
        return {
            "main": self.config.get("task_interval", self.default_interval),
            "responsibilities": self.config.get("responsibilities_interval", 300),
        }

    async def run_loop(self, loop_name: str) -> None:
        if loop_name == "responsibilities":
            await self.check_responsibilities()
        else:
            await self.run_once()

    async def check_responsibilities(self) -> None:
        from responsibilities.snapshot import build_pr_snapshot

        projects = self.config.get("projects", [])
        repos = [p["github_repo"] for p in projects]
        branch_prefixes = [p["branch_prefix"] for p in projects]
        branch_prefix = branch_prefixes[0] if branch_prefixes else "agent/"

        bot_login = await self.github.get_bot_login_async()

        snapshot = await build_pr_snapshot(self.github, repos, branch_prefix, bot_login)

        # Cleanup stale state entries
        open_pr_keys = {f"{pr['repo']}#PR{pr['number']}" for pr in snapshot.prs}
        self._state.cleanup(open_pr_keys)

        # Check responsibilities in priority order, handle first found item
        for responsibility in self._responsibilities:
            items = await responsibility.check(snapshot, self._state)
            for item in items:
                if await self._resp_claims.is_claimed(item.event_key):
                    continue
                if not await self._resp_claims.try_claim(item.event_key):
                    continue
                try:
                    logging.info(f"[{self.agent_id}] Handling responsibility: {item.kind} on {item.repo}#{item.pr_number}")
                    await responsibility.execute(item, self.github, self.asana, self.agent_id)
                    return  # one item per cycle
                finally:
                    await self._resp_claims.release(item.event_key)

        logging.info(f"[{self.agent_id}] No responsibilities to handle")

    async def run_once(self) -> None:
        projects = self.config.get("projects", [])
        assignee_gid = self.config.get("asana_assignee_gid")
        max_open_prs = self.config.get("max_open_prs", 15)
        claims = TaskClaims.get()

        # Rate-limit: skip cycle if too many agent PRs are open
        bot_login = await self.github.get_bot_login_async()
        repos = [p["github_repo"] for p in projects]
        branch_prefix = projects[0].get("branch_prefix", "agent/") if projects else "agent/"
        total_open = 0
        for repo in repos:
            open_prs = await self.github.get_open_prs_async(repo)
            total_open += sum(
                1 for pr in open_prs
                if pr["author_login"] == bot_login
                and pr["head_branch"].startswith(branch_prefix)
            )
        if total_open >= max_open_prs:
            logging.info(
                f"[{self.agent_id}] {total_open} open PRs (limit {max_open_prs}), pausing."
            )
            audit.log_event(
                "rate_limited",
                agent_id=self.agent_id,
                open_prs=total_open,
                max_open_prs=max_open_prs,
            )
            return

        all_tasks = []
        task_project_map: dict[str, dict] = {}
        repo_summaries: list[str] = []

        for project in projects:
            logging.info(
                f"[{self.agent_id}] Fetching tasks from project: {project['asana_project_id']}"
            )
            fetched = await self.asana.get_unassigned_tasks_async(
                project["asana_project_id"]
            )
            filtered = filter_and_rank_tasks(fetched, project)
            all_tasks.extend(filtered)
            for t in filtered:
                task_project_map[t["gid"]] = project
            logging.info(
                f"[{self.agent_id}] Fetching repo summary for {project['github_repo']}"
            )
            repo_summaries.append(
                await self.github.get_repo_summary_async(project["github_repo"])
            )

        # Filter out tasks already claimed by another agent
        unclaimed_tasks = []
        for t in all_tasks:
            if not await claims.is_claimed(t["gid"]):
                unclaimed_tasks.append(t)

        repo_context = "\n\n---\n\n".join(repo_summaries)
        task = await select_task(unclaimed_tasks, repo_context=repo_context)
        if task is None:
            logging.info(f"[{self.agent_id}] No feasible task found.")
            audit.log_event("no_task_found", agent_id=self.agent_id)
            return

        # Try to claim the selected task; if another agent beat us, give up this cycle
        if not await claims.try_claim(task["gid"]):
            logging.info(
                f"[{self.agent_id}] Task {task['gid']} already claimed by another agent, skipping."
            )
            audit.log_event(
                "task_claim_failed", agent_id=self.agent_id, task_gid=task["gid"]
            )
            return

        claimed_gid = task["gid"]
        try:
            logging.info(
                f"[{self.agent_id}] Selected task: [{task['gid']}] {task['name']}"
            )
            project_cfg = task_project_map[task["gid"]]
            repo = project_cfg["github_repo"]
            audit.log_event(
                "task_selected",
                agent_id=self.agent_id,
                task_gid=task["gid"],
                task_name=task["name"],
                repo=repo,
            )

            if self.dry_run:
                logging.info(f"[{self.agent_id}] dry-run — skipping implementation.")
                return

            branch = _branch_name(task, project_cfg["branch_prefix"])

            await self.asana.assign_task_async(task["gid"], assignee_gid)
            await self.asana.add_comment_async(
                task["gid"],
                f"I'm picking this up. Proposed approach: I'll analyse the codebase and implement a fix on branch `{branch}`. Will post the PR link here once done.",
            )

            start_time = time.monotonic()
            repo_path = await self.github.clone_repo_async(repo)
            try:
                await self.github.create_branch_async(repo_path, branch)
                import config

                prompt = build_agent_prompt(
                    task, repo, knowledge_dir=config.KNOWLEDGE_DIR
                )
                try:
                    result = await run_agent(repo_path, prompt)
                except AgentError as exc:
                    result = AgentResult(success=False, error=str(exc))

                elapsed_minutes = max(
                    1, math.ceil((time.monotonic() - start_time) / 60)
                )

                if not result.success:
                    await self.asana.assign_task_async(task["gid"], None)
                    await self.asana.add_comment_async(
                        task["gid"],
                        f"I ran into an error and could not complete this task:\n\n{result.error}",
                    )
                    await self._log_time(task["gid"], elapsed_minutes)
                    audit.log_event(
                        "implementation_failed",
                        agent_id=self.agent_id,
                        task_gid=task["gid"],
                        task_name=task["name"],
                        repo=repo,
                        error=result.error,
                        duration_minutes=elapsed_minutes,
                    )
                    return

                await self.github.commit_and_push_async(
                    repo_path, branch, f"fix: {task['name'][:72]}"
                )
                pr_url = await self.github.create_pr_async(
                    repo=repo,
                    branch=branch,
                    title=f"[SWEAT-AGENT]: {task['name'][:72]}",
                    body=f"## Summary\n\n{result.summary}\n\n**Asana task:** https://app.asana.com/0/0/{task['gid']}\n\n---\n_AI-generated by sweat agent_",
                )
                await self.asana.add_comment_async(task["gid"], f"PR opened: {pr_url}")
                await self._log_time(task["gid"], elapsed_minutes)
                audit.log_event(
                    "implementation_succeeded",
                    agent_id=self.agent_id,
                    task_gid=task["gid"],
                    task_name=task["name"],
                    repo=repo,
                    branch=branch,
                    pr_url=pr_url,
                    duration_minutes=elapsed_minutes,
                )
                logging.info(f"[{self.agent_id}] Done. PR: {pr_url}")
            finally:
                shutil.rmtree(repo_path, ignore_errors=True)
        finally:
            await claims.release(claimed_gid)

    async def _log_time(self, task_gid: str, duration_minutes: int) -> None:
        """Record actual time spent on the task in Asana's time tracking."""
        try:
            await self.asana.add_time_tracking_entry_async(
                task_gid, duration_minutes, date.today().isoformat()
            )
            logging.info(
                f"[{self.agent_id}] Logged {duration_minutes}m to task {task_gid}"
            )
        except Exception as exc:
            logging.warning(
                f"[{self.agent_id}] Failed to log time to task {task_gid}: {exc}"
            )
