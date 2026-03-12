from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pr_poller import poll_and_review


@patch("pr_poller.review_pr", new_callable=AsyncMock)
@patch("pr_poller.has_bot_reviewed")
@patch("pr_poller.get_open_prs")
@patch("pr_poller.get_bot_login")
@patch("pr_poller.config")
async def test_reviews_unreviewed_pr(mock_config, mock_login, mock_open_prs, mock_reviewed, mock_review):
    mock_config.PROJECTS = [{"github_repo": "org/repo", "branch_prefix": "agent/"}]
    mock_login.return_value = "sweat-bot"
    mock_open_prs.return_value = [
        {"number": 42, "title": "Add feature", "head_branch": "feature/cool", "html_url": "..."}
    ]
    mock_reviewed.return_value = False

    await poll_and_review()

    mock_review.assert_awaited_once_with("org/repo", 42)


@patch("pr_poller.review_pr", new_callable=AsyncMock)
@patch("pr_poller.has_bot_reviewed")
@patch("pr_poller.get_open_prs")
@patch("pr_poller.get_bot_login")
@patch("pr_poller.config")
async def test_skips_agent_branch_pr(mock_config, mock_login, mock_open_prs, mock_reviewed, mock_review):
    mock_config.PROJECTS = [{"github_repo": "org/repo", "branch_prefix": "agent/"}]
    mock_login.return_value = "sweat-bot"
    mock_open_prs.return_value = [
        {"number": 7, "title": "Bot PR", "head_branch": "agent/asana-123-fix", "html_url": "..."}
    ]
    mock_reviewed.return_value = False

    await poll_and_review()

    mock_review.assert_not_awaited()


@patch("pr_poller.review_pr", new_callable=AsyncMock)
@patch("pr_poller.has_bot_reviewed")
@patch("pr_poller.get_open_prs")
@patch("pr_poller.get_bot_login")
@patch("pr_poller.config")
async def test_skips_already_reviewed_pr(mock_config, mock_login, mock_open_prs, mock_reviewed, mock_review):
    mock_config.PROJECTS = [{"github_repo": "org/repo", "branch_prefix": "agent/"}]
    mock_login.return_value = "sweat-bot"
    mock_open_prs.return_value = [
        {"number": 5, "title": "Some PR", "head_branch": "fix/something", "html_url": "..."}
    ]
    mock_reviewed.return_value = True

    await poll_and_review()

    mock_review.assert_not_awaited()


@patch("pr_poller.review_pr", new_callable=AsyncMock)
@patch("pr_poller.has_bot_reviewed")
@patch("pr_poller.get_open_prs")
@patch("pr_poller.get_bot_login")
@patch("pr_poller.config")
async def test_iterates_all_configured_repos(mock_config, mock_login, mock_open_prs, mock_reviewed, mock_review):
    mock_config.PROJECTS = [
        {"github_repo": "org/repo-a", "branch_prefix": "agent/"},
        {"github_repo": "org/repo-b", "branch_prefix": "agent/"},
    ]
    mock_login.return_value = "sweat-bot"
    mock_open_prs.return_value = []

    await poll_and_review()

    assert mock_open_prs.call_count == 2
    repos_called = {call.args[0] for call in mock_open_prs.call_args_list}
    assert repos_called == {"org/repo-a", "org/repo-b"}
