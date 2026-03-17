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


@patch("clients.asana._Client")
def test_create_task_calls_api(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.tasks.create_task.return_value = {"gid": "999", "name": "New task"}

    client = AsanaClient("test-token")
    result = client.create_task("PROJECT_GID", "New task", "Some notes")

    mock_client.tasks.create_task.assert_called_once_with(
        {"name": "New task", "projects": ["PROJECT_GID"], "notes": "Some notes"}
    )
    assert result["gid"] == "999"


@patch("clients.asana._Client")
def test_create_task_with_html_notes(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.tasks.create_task.return_value = {"gid": "999", "name": "Task"}

    client = AsanaClient("test-token")
    client.create_task("PROJECT_GID", "Task", html_notes="<body>content</body>")

    call_body = mock_client.tasks.create_task.call_args[0][0]
    assert call_body["html_notes"] == "<body>content</body>"
    assert "notes" not in call_body


@patch("clients.asana._Client")
def test_create_task_with_estimated_minutes(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.tasks.create_task.return_value = {"gid": "999", "name": "Task"}

    client = AsanaClient("test-token")
    client.create_task("PROJECT_GID", "Task", estimated_minutes=60)

    call_body = mock_client.tasks.create_task.call_args[0][0]
    assert call_body["estimated_duration_minutes"] == 60


@patch("clients.asana._Client")
async def test_create_task_async_forwards_html_notes_and_estimated_minutes(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.tasks.create_task.return_value = {"gid": "999", "name": "Task"}

    client = AsanaClient("test-token")
    await client.create_task_async(
        "PROJECT_GID", "Task", html_notes="<body>html</body>", estimated_minutes=45
    )

    call_body = mock_client.tasks.create_task.call_args[0][0]
    assert call_body["html_notes"] == "<body>html</body>"
    assert "notes" not in call_body
    assert call_body["estimated_duration_minutes"] == 45


@patch("clients.asana._Client")
def test_get_tasks_returns_incomplete(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.tasks.get_tasks_for_project.return_value = [
        {"gid": "111", "name": "Open task", "completed": False},
        {"gid": "222", "name": "Done task", "completed": True},
        {"gid": "333", "name": "Another open", "completed": False},
    ]

    client = AsanaClient("test-token")
    tasks = client.get_tasks("PROJECT_GID")

    assert len(tasks) == 2
    assert tasks[0] == {"gid": "111", "name": "Open task"}
    assert tasks[1] == {"gid": "333", "name": "Another open"}
