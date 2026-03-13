from unittest.mock import MagicMock, patch

import pytest

from clients.asana import AsanaClient


@patch("clients.asana._Client")
def test_get_unassigned_tasks_returns_list(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.tasks.get_tasks_for_project.return_value = [
        {"gid": "111", "name": "Fix login bug", "notes": "Users can't log in", "completed": False},
        {"gid": "222", "name": "Add dark mode", "notes": "", "completed": False},
    ]
    mock_client.tasks.get_task.side_effect = lambda gid, **_: {
        "gid": gid,
        "name": "Fix login bug" if gid == "111" else "Add dark mode",
        "notes": "Users can't log in" if gid == "111" else "",
        "assignee": None,
    }

    client = AsanaClient("test-token")
    tasks = client.get_unassigned_tasks("PROJECT_GID")

    assert len(tasks) == 2
    assert tasks[0]["gid"] == "111"
    assert tasks[0]["assignee"] is None


@patch("clients.asana._Client")
def test_get_unassigned_tasks_filters_assigned(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.tasks.get_tasks_for_project.return_value = [
        {"gid": "111", "name": "Fix login bug", "completed": False},
    ]
    mock_client.tasks.get_task.return_value = {
        "gid": "111",
        "name": "Fix login bug",
        "notes": "",
        "assignee": {"gid": "someone"},
    }

    client = AsanaClient("test-token")
    tasks = client.get_unassigned_tasks("PROJECT_GID")

    assert tasks == []


@patch("clients.asana._Client")
def test_get_unassigned_tasks_filters_completed(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.tasks.get_tasks_for_project.return_value = [
        {"gid": "111", "name": "Done task", "completed": True},
        {"gid": "222", "name": "Open task", "completed": False},
    ]
    mock_client.tasks.get_task.return_value = {
        "gid": "222",
        "name": "Open task",
        "notes": "",
        "assignee": None,
    }

    client = AsanaClient("test-token")
    tasks = client.get_unassigned_tasks("PROJECT_GID")

    assert len(tasks) == 1
    assert tasks[0]["gid"] == "222"
    mock_client.tasks.get_task.assert_called_once()


@patch("clients.asana._Client")
def test_assign_task_calls_api(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    client = AsanaClient("test-token")
    client.assign_task("TASK_GID", "USER_GID")

    mock_client.tasks.update_task.assert_called_once_with(
        "TASK_GID", {"assignee": "USER_GID"}, opt_pretty=True
    )


@patch("clients.asana._Client")
def test_add_comment_calls_api(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    client = AsanaClient("test-token")
    client.add_comment("TASK_GID", "Hello from agent")

    mock_client.stories.create_story_for_task.assert_called_once_with(
        "TASK_GID", {"text": "Hello from agent"}, opt_pretty=True
    )


@patch("clients.asana._Client")
def test_add_time_tracking_entry_calls_api(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    client = AsanaClient("test-token")
    client.add_time_tracking_entry("TASK_GID", 42, "2026-03-13")

    mock_client.time_tracking.create_time_tracking_entry.assert_called_once_with(
        "TASK_GID", {"duration_minutes": 42, "entered_on": "2026-03-13"}
    )
