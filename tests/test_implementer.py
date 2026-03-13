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
    github.get_repo_summary_async = AsyncMock()
    github.clone_repo_async = AsyncMock()
    github.create_branch_async = AsyncMock()
    github.commit_and_push_async = AsyncMock()
    github.create_pr_async = AsyncMock()
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
