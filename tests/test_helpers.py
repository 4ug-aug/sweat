from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent import AgentResult
from clients.github import GitHubClient
from exceptions import AgentError


async def test_work_on_branch_success():
    github = MagicMock(spec=GitHubClient)
    github.clone_repo_async = AsyncMock(return_value="/tmp/repo")
    github.checkout_branch_async = AsyncMock()
    github.commit_and_push_async = AsyncMock()

    with patch("agents.helpers.run_agent", new=AsyncMock(return_value=AgentResult(success=True, summary="done"))):
        from agents.helpers import work_on_branch
        result = await work_on_branch(github, "org/repo", "branch", "prompt", "fix: feedback")

    assert result.success is True
    github.clone_repo_async.assert_called_once_with("org/repo")
    github.checkout_branch_async.assert_called_once_with("/tmp/repo", "branch")
    github.commit_and_push_async.assert_called_once_with("/tmp/repo", "branch", "fix: feedback")


async def test_work_on_branch_failure_skips_commit():
    github = MagicMock(spec=GitHubClient)
    github.clone_repo_async = AsyncMock(return_value="/tmp/repo")
    github.checkout_branch_async = AsyncMock()
    github.commit_and_push_async = AsyncMock()

    with patch("agents.helpers.run_agent", new=AsyncMock(return_value=AgentResult(success=False, error="oops"))):
        from agents.helpers import work_on_branch
        result = await work_on_branch(github, "org/repo", "branch", "prompt")

    assert result.success is False
    github.commit_and_push_async.assert_not_called()


async def test_work_on_branch_agent_error_returns_failed_result():
    github = MagicMock(spec=GitHubClient)
    github.clone_repo_async = AsyncMock(return_value="/tmp/repo")
    github.checkout_branch_async = AsyncMock()
    github.commit_and_push_async = AsyncMock()

    with patch("agents.helpers.run_agent", new=AsyncMock(side_effect=AgentError("auth failed"))):
        from agents.helpers import work_on_branch
        result = await work_on_branch(github, "org/repo", "branch", "prompt")

    assert result.success is False
    assert "auth failed" in result.error
    github.commit_and_push_async.assert_not_called()


async def test_work_on_branch_cleanup_always_runs():
    github = MagicMock(spec=GitHubClient)
    github.clone_repo_async = AsyncMock(return_value="/tmp/repo")
    github.checkout_branch_async = AsyncMock(side_effect=Exception("checkout failed"))
    github.commit_and_push_async = AsyncMock()

    with patch("agents.helpers.shutil") as mock_shutil:
        with patch("agents.helpers.run_agent", new=AsyncMock(return_value=AgentResult(success=True))):
            from agents.helpers import work_on_branch
            try:
                await work_on_branch(github, "org/repo", "branch", "prompt")
            except Exception:
                pass
        mock_shutil.rmtree.assert_called_once_with("/tmp/repo", ignore_errors=True)
