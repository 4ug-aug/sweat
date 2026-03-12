import logging

import audit
from agent import run_agent
from github_client import get_pr_diff, get_pr_metadata, get_repo_summary, post_pr_review
from prompts.review_prompt import build_review_prompt

_MAX_DIFF_CHARS = 40_000


async def review_pr(repo: str, pr_number: int) -> None:
    meta = get_pr_metadata(repo, pr_number)
    diff = get_pr_diff(repo, pr_number)[:_MAX_DIFF_CHARS]
    repo_summary = get_repo_summary(repo)
    prompt = build_review_prompt(meta, diff, repo_summary)
    result = await run_agent(repo_path=None, prompt=prompt)
    if result.success and result.summary:
        post_pr_review(repo, pr_number, body=result.summary)
        audit.log_event("pr_review_posted", repo=repo, pr_number=pr_number, pr_title=meta["title"])
        logging.info(f"Posted review on PR #{pr_number} in {repo}")
    else:
        audit.log_event("pr_review_failed", repo=repo, pr_number=pr_number, error=result.error)
        logging.warning(f"Agent failed for PR #{pr_number}: {result.error}")
