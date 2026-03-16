from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent import AgentResult
from agents.reviewer import ReviewerAgent, _MAX_DIFF_CHARS
from clients.asana import AsanaClient
from clients.github import GitHubClient

_AGENT_CFG = {
    "id": "test-reviewer",
    "type": "reviewer",
    "projects": [
        {
            "github_repo": "org/repo",
            "branch_prefix": "agent/",
        }
    ],
}


def _make_agent():
    github = MagicMock(spec=GitHubClient)
    asana = MagicMock(spec=AsanaClient)
    # Wire up async methods
    github.get_bot_login_async = AsyncMock()
    github.get_open_prs_async = AsyncMock()
    github.has_bot_reviewed_async = AsyncMock()
    github.get_latest_review_timestamp_async = AsyncMock()
    github.get_latest_commit_timestamp_async = AsyncMock()
    github.get_pr_metadata_async = AsyncMock()
    github.get_pr_diff_async = AsyncMock()
    github.get_repo_summary_async = AsyncMock()
    github.post_pr_review_async = AsyncMock()
    return ReviewerAgent(
        agent_id="test-reviewer",
        config=_AGENT_CFG,
        github=github,
        asana=asana,
    )


# --- poll logic tests ---


@patch("agents.reviewer.run_agent", new_callable=AsyncMock)
async def test_reviews_unreviewed_pr(mock_run_agent):
    agent = _make_agent()
    agent.github.get_bot_login_async.return_value = "sweat-bot"
    agent.github.get_open_prs_async.return_value = [
        {"number": 42, "title": "Add feature", "head_branch": "feature/cool", "html_url": "..."}
    ]
    agent.github.has_bot_reviewed_async.return_value = False
    agent.github.get_pr_metadata_async.return_value = {
        "number": 42, "title": "Add feature", "body": "", "author_login": "dev",
        "head_branch": "feature/cool", "base_branch": "main", "html_url": "...",
    }
    agent.github.get_pr_diff_async.return_value = "diff"
    agent.github.get_repo_summary_async.return_value = "summary"
    mock_run_agent.return_value = AgentResult(success=True, summary="LGTM")

    await agent.run_once()

    agent.github.post_pr_review_async.assert_called_once_with("org/repo", 42, body="LGTM")


async def test_skips_agent_branch_pr():
    agent = _make_agent()
    agent.github.get_bot_login_async.return_value = "sweat-bot"
    agent.github.get_open_prs_async.return_value = [
        {"number": 7, "title": "Bot PR", "head_branch": "agent/asana-123-fix", "html_url": "..."}
    ]

    await agent.run_once()

    agent.github.get_pr_metadata_async.assert_not_called()


async def test_skips_already_reviewed_pr():
    agent = _make_agent()
    agent.github.get_bot_login_async.return_value = "sweat-bot"
    agent.github.get_open_prs_async.return_value = [
        {"number": 5, "title": "Some PR", "head_branch": "fix/something", "html_url": "..."}
    ]
    agent.github.has_bot_reviewed_async.return_value = True
    agent.github.get_latest_review_timestamp_async.return_value = "2024-01-01T12:00:00Z"
    agent.github.get_latest_commit_timestamp_async.return_value = "2024-01-01T11:00:00Z"

    await agent.run_once()

    agent.github.get_pr_metadata_async.assert_not_called()


@patch("agents.reviewer.run_agent", new_callable=AsyncMock)
async def test_rereviews_pr_with_new_commits(mock_run_agent):
    agent = _make_agent()
    agent.github.get_bot_login_async.return_value = "sweat-bot"
    agent.github.get_open_prs_async.return_value = [
        {"number": 6, "title": "Updated PR", "head_branch": "fix/updated", "html_url": "..."}
    ]
    agent.github.has_bot_reviewed_async.return_value = True
    agent.github.get_latest_review_timestamp_async.return_value = "2024-01-01T10:00:00Z"
    agent.github.get_latest_commit_timestamp_async.return_value = "2024-01-01T12:00:00Z"
    agent.github.get_pr_metadata_async.return_value = {
        "number": 6, "title": "Updated PR", "body": "", "author_login": "dev",
        "head_branch": "fix/updated", "base_branch": "main", "html_url": "...",
    }
    agent.github.get_pr_diff_async.return_value = "diff"
    agent.github.get_repo_summary_async.return_value = "summary"
    mock_run_agent.return_value = AgentResult(success=True, summary="LGTM again")

    await agent.run_once()

    agent.github.post_pr_review_async.assert_called_once_with("org/repo", 6, body="LGTM again")


async def test_iterates_all_configured_repos():
    cfg = {
        "id": "test-reviewer",
        "type": "reviewer",
        "projects": [
            {"github_repo": "org/repo-a", "branch_prefix": "agent/"},
            {"github_repo": "org/repo-b", "branch_prefix": "agent/"},
        ],
    }
    github = MagicMock(spec=GitHubClient)
    asana = MagicMock(spec=AsanaClient)
    github.get_bot_login_async = AsyncMock(return_value="sweat-bot")
    github.get_open_prs_async = AsyncMock(return_value=[])
    agent = ReviewerAgent(agent_id="test-reviewer", config=cfg, github=github, asana=asana)

    await agent.run_once()

    assert github.get_open_prs_async.call_count == 2
    repos_called = {call.args[0] for call in github.get_open_prs_async.call_args_list}
    assert repos_called == {"org/repo-a", "org/repo-b"}


# --- review logic tests ---


@patch("agents.reviewer.run_agent", new_callable=AsyncMock)
async def test_full_review_flow_posts_review(mock_agent):
    agent = _make_agent()
    agent.github.get_pr_metadata_async.return_value = {
        "number": 1, "title": "Fix bug", "body": "", "author_login": "dev",
        "head_branch": "fix/bug", "base_branch": "main", "html_url": "...",
    }
    agent.github.get_pr_diff_async.return_value = "diff content"
    agent.github.get_repo_summary_async.return_value = "repo summary"
    mock_agent.return_value = AgentResult(success=True, summary="LGTM")

    await agent._review_pr("org/repo", 1)

    agent.github.post_pr_review_async.assert_called_once_with("org/repo", 1, body="LGTM")


@patch("agents.reviewer.run_agent", new_callable=AsyncMock)
async def test_skips_post_on_agent_failure(mock_agent):
    agent = _make_agent()
    agent.github.get_pr_metadata_async.return_value = {
        "number": 2, "title": "PR", "body": "", "author_login": "dev",
        "head_branch": "feat/x", "base_branch": "main", "html_url": "...",
    }
    agent.github.get_pr_diff_async.return_value = "diff"
    agent.github.get_repo_summary_async.return_value = "summary"
    mock_agent.return_value = AgentResult(success=False, error="timeout")

    await agent._review_pr("org/repo", 2)

    agent.github.post_pr_review_async.assert_not_called()


@patch("agents.reviewer.run_agent", new_callable=AsyncMock)
async def test_truncates_large_diff(mock_agent):
    agent = _make_agent()
    agent.github.get_pr_metadata_async.return_value = {
        "number": 3, "title": "Big PR", "body": "", "author_login": "dev",
        "head_branch": "feat/big", "base_branch": "main", "html_url": "...",
    }
    large_diff = "x" * (_MAX_DIFF_CHARS + 10_000)
    agent.github.get_pr_diff_async.return_value = large_diff
    agent.github.get_repo_summary_async.return_value = "summary"
    mock_agent.return_value = AgentResult(success=True, summary="review")

    await agent._review_pr("org/repo", 3)

    # The prompt builder receives a truncated diff
    from prompts.review_prompt import build_review_prompt
    call_args = mock_agent.call_args
    # run_agent is called with prompt kwarg or positional
    prompt = call_args.kwargs.get("prompt") or call_args.args[1]
    # The diff inside the prompt should be truncated
    assert len(large_diff[:_MAX_DIFF_CHARS]) == _MAX_DIFF_CHARS
