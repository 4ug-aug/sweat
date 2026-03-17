from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.implementer import ImplementerAgent
from clients.asana import AsanaClient
from clients.github import GitHubClient
from task_claims import TaskClaims

_AGENT_CFG = {
    "id": "test-impl",
    "type": "implementer",
    "asana_assignee_gid": "ASSIGNEE_GID",
    "projects": [
        {
            "asana_project_id": "PROJ1",
            "github_repo": "org/repo",
            "branch_prefix": "agent/",
            "field_names": {},
            "field_filters": {},
            "priority_order": [],
            "max_tasks_for_selector": 20,
        }
    ],
}

_TASK = {"gid": "111", "name": "Fix login bug", "notes": "desc"}


@pytest.fixture(autouse=True)
def reset_claims():
    TaskClaims._instance = None
    yield
    TaskClaims._instance = None


def _make_agent(dry_run=False):
    github = MagicMock(spec=GitHubClient)
    asana = MagicMock(spec=AsanaClient)
    # Wire up async methods as AsyncMocks
    asana.get_unassigned_tasks_async = AsyncMock()
    asana.assign_task_async = AsyncMock()
    asana.add_comment_async = AsyncMock()
    asana.add_time_tracking_entry_async = AsyncMock()
    github.get_repo_summary_async = AsyncMock()
    github.clone_repo_async = AsyncMock()
    github.create_branch_async = AsyncMock()
    github.commit_and_push_async = AsyncMock()
    github.create_pr_async = AsyncMock()
    github.get_bot_login_async = AsyncMock(return_value="sweat-bot")
    github.get_open_prs_async = AsyncMock(return_value=[])
    agent = ImplementerAgent(
        agent_id="test-impl",
        config=_AGENT_CFG,
        github=github,
        asana=asana,
        dry_run=dry_run,
    )
    return agent


@patch("agents.implementer.filter_and_rank_tasks", side_effect=lambda tasks, _cfg: tasks)
@patch("agents.implementer.run_agent", new_callable=AsyncMock)
@patch("agents.implementer.select_task", new_callable=AsyncMock)
async def test_run_once_full_flow(mock_select, mock_run_agent, mock_filter):
    agent = _make_agent()
    agent.asana.get_unassigned_tasks_async.return_value = [_TASK]
    agent.github.get_repo_summary_async.return_value = "## File tree\nfoo.py"
    agent.github.clone_repo_async.return_value = "/tmp/sweat_abc"
    agent.github.create_pr_async.return_value = "https://github.com/org/repo/pull/1"
    mock_select.return_value = _TASK
    mock_run_agent.return_value = MagicMock(success=True, summary="Fixed auth module")

    await agent.run_once()

    agent.asana.assign_task_async.assert_called_once()
    mock_run_agent.assert_called_once()
    agent.github.create_pr_async.assert_called_once()
    assert agent.asana.add_comment_async.call_count == 2
    agent.asana.add_time_tracking_entry_async.assert_called_once()
    mock_select.assert_called_once_with([_TASK], repo_context="## File tree\nfoo.py")


@patch("agents.implementer.select_task", new_callable=AsyncMock)
async def test_run_once_exits_cleanly_when_no_task(mock_select):
    agent = _make_agent()
    agent.asana.get_unassigned_tasks_async.return_value = []
    agent.github.get_repo_summary_async.return_value = ""
    mock_select.return_value = None

    await agent.run_once()


@patch("agents.implementer.filter_and_rank_tasks", side_effect=lambda tasks, _cfg: tasks)
@patch("agents.implementer.select_task", new_callable=AsyncMock)
async def test_dry_run_does_not_assign_or_clone(mock_select, mock_filter):
    agent = _make_agent(dry_run=True)
    agent.asana.get_unassigned_tasks_async.return_value = [_TASK]
    agent.github.get_repo_summary_async.return_value = "## File tree\nfoo.py"
    mock_select.return_value = _TASK

    await agent.run_once()

    agent.asana.assign_task_async.assert_not_called()
    agent.github.clone_repo_async.assert_not_called()


@patch("agents.implementer.filter_and_rank_tasks", side_effect=lambda tasks, _cfg: tasks)
@patch("agents.implementer.run_agent", new_callable=AsyncMock)
@patch("agents.implementer.select_task", new_callable=AsyncMock)
async def test_run_once_posts_error_on_agent_failure(mock_select, mock_run_agent, mock_filter):
    agent = _make_agent()
    agent.asana.get_unassigned_tasks_async.return_value = [_TASK]
    agent.github.get_repo_summary_async.return_value = "## File tree\nfoo.py"
    agent.github.clone_repo_async.return_value = "/tmp/sweat_abc"
    mock_select.return_value = _TASK
    mock_run_agent.return_value = MagicMock(success=False, error="Agent crashed")

    await agent.run_once()

    assert agent.asana.assign_task_async.call_count == 2
    second_call_args = agent.asana.assign_task_async.call_args_list[1]
    assert second_call_args[0][1] is None
    assert agent.asana.add_comment_async.call_count == 2
    agent.asana.add_time_tracking_entry_async.assert_called_once()
    agent.github.create_pr_async.assert_not_called()


@patch("agents.implementer.filter_and_rank_tasks", side_effect=lambda tasks, _cfg: tasks)
@patch("agents.implementer.select_task", new_callable=AsyncMock)
async def test_claimed_tasks_are_filtered_out(mock_select, mock_filter):
    """Tasks already claimed by another agent should not be passed to select_task."""
    claims = TaskClaims.get()
    await claims.try_claim("111")

    agent = _make_agent()
    agent.asana.get_unassigned_tasks_async.return_value = [_TASK]
    agent.github.get_repo_summary_async.return_value = ""
    mock_select.return_value = None

    await agent.run_once()

    # select_task should receive an empty list since _TASK is claimed
    mock_select.assert_called_once_with([], repo_context="")


@patch("agents.implementer.filter_and_rank_tasks", side_effect=lambda tasks, _cfg: tasks)
@patch("agents.implementer.run_agent", new_callable=AsyncMock)
@patch("agents.implementer.select_task", new_callable=AsyncMock)
async def test_claim_released_after_run(mock_select, mock_run_agent, mock_filter):
    """The task claim is released after run_once completes (success or failure)."""
    agent = _make_agent()
    agent.asana.get_unassigned_tasks_async.return_value = [_TASK]
    agent.github.get_repo_summary_async.return_value = ""
    agent.github.clone_repo_async.return_value = "/tmp/sweat_abc"
    agent.github.create_pr_async.return_value = "https://github.com/org/repo/pull/1"
    mock_select.return_value = _TASK
    mock_run_agent.return_value = MagicMock(success=True, summary="done")

    await agent.run_once()

    claims = TaskClaims.get()
    assert await claims.is_claimed("111") is False


@patch("agents.implementer.filter_and_rank_tasks", side_effect=lambda tasks, _cfg: tasks)
@patch("agents.implementer.run_agent", new_callable=AsyncMock)
@patch("agents.implementer.select_task", new_callable=AsyncMock)
async def test_time_tracking_entry_logged_with_today(mock_select, mock_run_agent, mock_filter):
    """Time tracking entry uses today's date and at least 1 minute."""
    agent = _make_agent()
    agent.asana.get_unassigned_tasks_async.return_value = [_TASK]
    agent.github.get_repo_summary_async.return_value = ""
    agent.github.clone_repo_async.return_value = "/tmp/sweat_abc"
    agent.github.create_pr_async.return_value = "https://github.com/org/repo/pull/1"
    mock_select.return_value = _TASK
    mock_run_agent.return_value = MagicMock(success=True, summary="done")

    await agent.run_once()

    call_args = agent.asana.add_time_tracking_entry_async.call_args
    assert call_args[0][0] == "111"
    assert call_args[0][1] >= 1  # at least 1 minute
    assert call_args[0][2] == date.today().isoformat()


@patch("agents.implementer.filter_and_rank_tasks", side_effect=lambda tasks, _cfg: tasks)
@patch("agents.implementer.run_agent", new_callable=AsyncMock)
@patch("agents.implementer.select_task", new_callable=AsyncMock)
async def test_time_tracking_failure_does_not_crash_agent(mock_select, mock_run_agent, mock_filter):
    """If the time tracking API call fails, the agent should still complete."""
    agent = _make_agent()
    agent.asana.get_unassigned_tasks_async.return_value = [_TASK]
    agent.github.get_repo_summary_async.return_value = ""
    agent.github.clone_repo_async.return_value = "/tmp/sweat_abc"
    agent.github.create_pr_async.return_value = "https://github.com/org/repo/pull/1"
    agent.asana.add_time_tracking_entry_async.side_effect = Exception("API error")
    mock_select.return_value = _TASK
    mock_run_agent.return_value = MagicMock(success=True, summary="done")

    await agent.run_once()

    # PR should still be created despite time tracking failure
    agent.github.create_pr_async.assert_called_once()


async def test_rate_limited_when_too_many_open_prs():
    """Agent skips cycle when open agent PRs >= max_open_prs."""
    agent = _make_agent()
    agent.github.get_open_prs_async.return_value = [
        {"number": i, "title": f"PR {i}", "author_login": "sweat-bot", "head_branch": "agent/task-1", "base_branch": "main", "html_url": f"https://github.com/org/repo/pull/{i}"}
        for i in range(3)
    ]
    agent.config = {**_AGENT_CFG, "max_open_prs": 3}

    await agent.run_once()

    # Should not attempt to fetch tasks
    agent.asana.get_unassigned_tasks_async.assert_not_called()


async def test_not_rate_limited_when_under_limit():
    """Agent proceeds when open agent PRs < max_open_prs."""
    agent = _make_agent()
    agent.github.get_open_prs_async.return_value = [
        {"number": 1, "title": "PR 1", "author_login": "sweat-bot", "head_branch": "agent/task-1", "base_branch": "main", "html_url": "https://github.com/org/repo/pull/1"}
    ]

    agent.asana.get_unassigned_tasks_async.return_value = []
    agent.github.get_repo_summary_async.return_value = ""

    with patch("agents.implementer.select_task", new_callable=AsyncMock, return_value=None):
        await agent.run_once()

    # Should proceed to fetch tasks
    agent.asana.get_unassigned_tasks_async.assert_called_once()
