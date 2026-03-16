import shutil

from agent import AgentResult, run_agent
from clients.github import GitHubClient
from exceptions import AgentError


async def work_on_branch(
    github: GitHubClient,
    repo: str,
    branch: str,
    prompt: str,
    commit_message: str = "address feedback",
) -> AgentResult:
    """Clone repo, checkout branch, run Claude, commit and push. Returns AgentResult."""
    repo_path = await github.clone_repo_async(repo)
    try:
        await github.checkout_branch_async(repo_path, branch)
        try:
            result = await run_agent(repo_path, prompt)
        except AgentError as exc:
            return AgentResult(success=False, error=str(exc))
        if result.success:
            await github.commit_and_push_async(repo_path, branch, commit_message)
        return result
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)
