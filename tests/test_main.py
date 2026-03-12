# tests/test_main.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest
from main import run


@patch("main.add_comment")
@patch("main.create_pr")
@patch("main.commit_and_push")
@patch("main.create_branch")
@patch("main.run_agent")
@patch("main.clone_repo")
@patch("main.assign_task")
@patch("main.select_task")
@patch("main.get_unassigned_tasks")
async def test_run_full_flow(
    mock_get_tasks, mock_select, mock_assign,
    mock_clone, mock_run_agent, mock_create_branch,
    mock_commit_push, mock_create_pr, mock_add_comment
):
    mock_get_tasks.return_value = [{"gid": "111", "name": "Fix login bug", "notes": "desc"}]
    mock_select.return_value = {"gid": "111", "name": "Fix login bug", "notes": "desc"}
    mock_clone.return_value = "/tmp/sweat_abc"
    mock_run_agent.return_value = MagicMock(success=True, summary="Fixed auth module")
    mock_create_pr.return_value = "https://github.com/augusttollerup/repo/pull/1"

    await run(dry_run=False)

    mock_assign.assert_called_once()
    mock_run_agent.assert_called_once()
    mock_create_pr.assert_called_once()
    # Comment posted twice: proposal before, PR link after
    assert mock_add_comment.call_count == 2


@patch("main.get_unassigned_tasks")
async def test_run_exits_cleanly_when_no_task(mock_get_tasks):
    mock_get_tasks.return_value = []
    # Should not raise
    await run(dry_run=False)


@patch("main.select_task")
@patch("main.get_unassigned_tasks")
async def test_dry_run_does_not_assign_or_clone(mock_get_tasks, mock_select):
    mock_get_tasks.return_value = [{"gid": "111", "name": "Fix login bug", "notes": "desc"}]
    mock_select.return_value = {"gid": "111", "name": "Fix login bug", "notes": "desc"}

    with patch("main.assign_task") as mock_assign, patch("main.clone_repo") as mock_clone:
        await run(dry_run=True)
        mock_assign.assert_not_called()
        mock_clone.assert_not_called()
