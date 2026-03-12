import asyncio
import logging

import audit
import config
from github_client import get_bot_login, get_open_prs, has_bot_reviewed
from pr_reviewer import review_pr

_SWEAT_PREFIXES = tuple(p["branch_prefix"] for p in config.PROJECTS)


async def poll_and_review() -> None:
    bot_login = get_bot_login()
    configured_repos = {p["github_repo"] for p in config.PROJECTS}
    for repo in configured_repos:
        prs = get_open_prs(repo)
        for pr in prs:
            if pr["head_branch"].startswith(_SWEAT_PREFIXES):
                logging.info(f"Skipping self-authored PR #{pr['number']}: {pr['head_branch']}")
                audit.log_event("pr_skipped", repo=repo, pr_number=pr["number"], reason="self_authored")
                continue
            if has_bot_reviewed(repo, pr["number"], bot_login):
                logging.info(f"Already reviewed PR #{pr['number']}, skipping")
                audit.log_event("pr_skipped", repo=repo, pr_number=pr["number"], reason="already_reviewed")
                continue
            logging.info(f"Reviewing PR #{pr['number']}: {pr['title']}")
            await review_pr(repo, pr["number"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(poll_and_review())
