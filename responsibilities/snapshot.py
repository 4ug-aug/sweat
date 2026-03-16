from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clients.github import GitHubClient


@dataclass
class PRSnapshot:
    """Pre-fetched PR state for a single cycle, shared across all responsibilities."""
    prs: list[dict]                          # open PRs matching branch_prefix, each augmented with "repo" key
    reviews: dict[int, list[dict]]           # pr_number -> reviews
    check_status: dict[int, str]             # pr_number -> CI status string
    comment_threads: dict[int, list[dict]]   # pr_number -> comment threads
    bot_login: str = ""                      # authenticated bot login


async def build_pr_snapshot(
    github: "GitHubClient",
    repos: list[str],
    branch_prefix: str,
    bot_login: str,
) -> PRSnapshot:
    """Fetch open self-authored PRs with reviews, CI status, and comments."""
    all_prs: list[dict] = []

    for repo in repos:
        open_prs = await github.get_open_prs_async(repo)
        for pr in open_prs:
            if pr["head_branch"].startswith(branch_prefix):
                all_prs.append({**pr, "repo": repo})

    if not all_prs:
        return PRSnapshot(prs=[], reviews={}, check_status={}, comment_threads={}, bot_login=bot_login)

    # Fetch reviews, check_status, comment_threads for each PR in parallel
    async def fetch_pr_data(pr: dict) -> tuple[int, list[dict], str, list[dict]]:
        repo = pr["repo"]
        pr_number = pr["number"]
        reviews, status, threads = await asyncio.gather(
            github.get_pr_reviews_async(repo, pr_number),
            github.get_pr_check_status_async(repo, pr_number),
            github.get_pr_comment_threads_async(repo, pr_number),
        )
        return pr_number, reviews, status, threads

    results = await asyncio.gather(*[fetch_pr_data(pr) for pr in all_prs])

    reviews: dict[int, list[dict]] = {}
    check_status: dict[int, str] = {}
    comment_threads: dict[int, list[dict]] = {}

    for pr_number, pr_reviews, pr_status, pr_threads in results:
        reviews[pr_number] = pr_reviews
        check_status[pr_number] = pr_status
        comment_threads[pr_number] = pr_threads

    return PRSnapshot(
        prs=all_prs,
        reviews=reviews,
        check_status=check_status,
        comment_threads=comment_threads,
        bot_login=bot_login,
    )
