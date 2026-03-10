from unittest.mock import MagicMock, patch
import pytest
from asana_client import get_unassigned_tasks, assign_task, add_comment


@patch("asana_client.asana.Client")
def test_get_unassigned_tasks_returns_list(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.access_token.return_value = mock_client
    mock_client.tasks.get_tasks_for_project.return_value = [
        {"gid": "111", "name": "Fix login bug", "notes": "Users can't log in"},
        {"gid": "222", "name": "Add dark mode", "notes": ""},
    ]
    mock_client.tasks.get_task.side_effect = lambda gid, **_: {
        "gid": gid,
        "name": "Fix login bug" if gid == "111" else "Add dark mode",
        "notes": "Users can't log in" if gid == "111" else "",
        "assignee": None,
    }

    tasks = get_unassigned_tasks("PROJECT_GID")

    assert len(tasks) == 2
    assert tasks[0]["gid"] == "111"
    assert tasks[0]["assignee"] is None


@patch("asana_client.asana.Client")
def test_get_unassigned_tasks_filters_assigned(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.access_token.return_value = mock_client
    mock_client.tasks.get_tasks_for_project.return_value = [
        {"gid": "111", "name": "Fix login bug"},
    ]
    mock_client.tasks.get_task.return_value = {
        "gid": "111",
        "name": "Fix login bug",
        "notes": "",
        "assignee": {"gid": "someone"},
    }

    tasks = get_unassigned_tasks("PROJECT_GID")

    assert tasks == []


@patch("asana_client.asana.Client")
def test_assign_task_calls_api(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.access_token.return_value = mock_client

    assign_task("TASK_GID", "USER_GID")

    mock_client.tasks.update_task.assert_called_once_with(
        "TASK_GID", {"assignee": "USER_GID"}, opt_pretty=True
    )


@patch("asana_client.asana.Client")
def test_add_comment_calls_api(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.access_token.return_value = mock_client

    add_comment("TASK_GID", "Hello from agent")

    mock_client.stories.create_story_for_task.assert_called_once_with(
        "TASK_GID", {"text": "Hello from agent"}, opt_pretty=True
    )
