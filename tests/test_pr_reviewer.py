from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from agent import AgentResult
from pr_reviewer import review_pr, _MAX_DIFF_CHARS


@patch("pr_reviewer.post_pr_review")
@patch("pr_reviewer.run_agent", new_callable=AsyncMock)
@patch("pr_reviewer.build_review_prompt")
@patch("pr_reviewer.get_repo_summary")
@patch("pr_reviewer.get_pr_diff")
@patch("pr_reviewer.get_pr_metadata")
async def test_full_flow_posts_review(mock_meta, mock_diff, mock_summary, mock_prompt, mock_agent, mock_post):
    mock_meta.return_value = {"number": 1, "title": "Fix bug", "body": "", "author_login": "dev",
                              "head_branch": "fix/bug", "base_branch": "main", "html_url": "..."}
    mock_diff.return_value = "diff content"
    mock_summary.return_value = "repo summary"
    mock_prompt.return_value = "review prompt"
    mock_agent.return_value = AgentResult(success=True, summary="LGTM")

    await review_pr("org/repo", 1)

    mock_post.assert_called_once_with("org/repo", 1, body="LGTM")


@patch("pr_reviewer.post_pr_review")
@patch("pr_reviewer.run_agent", new_callable=AsyncMock)
@patch("pr_reviewer.build_review_prompt")
@patch("pr_reviewer.get_repo_summary")
@patch("pr_reviewer.get_pr_diff")
@patch("pr_reviewer.get_pr_metadata")
async def test_skips_post_on_agent_failure(mock_meta, mock_diff, mock_summary, mock_prompt, mock_agent, mock_post):
    mock_meta.return_value = {"number": 2, "title": "PR", "body": "", "author_login": "dev",
                              "head_branch": "feat/x", "base_branch": "main", "html_url": "..."}
    mock_diff.return_value = "diff"
    mock_summary.return_value = "summary"
    mock_prompt.return_value = "prompt"
    mock_agent.return_value = AgentResult(success=False, error="timeout")

    await review_pr("org/repo", 2)

    mock_post.assert_not_called()


@patch("pr_reviewer.post_pr_review")
@patch("pr_reviewer.run_agent", new_callable=AsyncMock)
@patch("pr_reviewer.build_review_prompt")
@patch("pr_reviewer.get_repo_summary")
@patch("pr_reviewer.get_pr_diff")
@patch("pr_reviewer.get_pr_metadata")
async def test_truncates_large_diff(mock_meta, mock_diff, mock_summary, mock_prompt, mock_agent, mock_post):
    mock_meta.return_value = {"number": 3, "title": "Big PR", "body": "", "author_login": "dev",
                              "head_branch": "feat/big", "base_branch": "main", "html_url": "..."}
    large_diff = "x" * (_MAX_DIFF_CHARS + 10_000)
    mock_diff.return_value = large_diff
    mock_summary.return_value = "summary"
    mock_agent.return_value = AgentResult(success=True, summary="review")

    await review_pr("org/repo", 3)

    called_diff = mock_prompt.call_args.args[1]
    assert len(called_diff) == _MAX_DIFF_CHARS
