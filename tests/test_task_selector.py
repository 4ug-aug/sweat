from unittest.mock import MagicMock, patch
import pytest
from task_selector import select_task

TASKS = [
    {"gid": "111", "name": "Fix login bug", "notes": "Users can't log in on /api/auth"},
    {"gid": "222", "name": "Add dark mode", "notes": ""},
    {"gid": "333", "name": "Write Q3 roadmap", "notes": "Business planning doc"},
]


@patch("task_selector.query")
def test_select_task_returns_task_when_feasible(mock_query):
    async def fake_messages():
        msg = MagicMock()
        msg.content = [MagicMock(text='{"task_gid": "111", "reason": "Clear bug with reproduction"}')]
        yield msg

    mock_query.return_value = fake_messages()

    result = select_task(TASKS)

    assert result is not None
    assert result["gid"] == "111"


@patch("task_selector.query")
def test_select_task_returns_none_when_no_feasible_task(mock_query):
    async def fake_messages():
        msg = MagicMock()
        msg.content = [MagicMock(text='{"task_gid": null, "reason": "All tasks are too vague"}')]
        yield msg

    mock_query.return_value = fake_messages()

    result = select_task(TASKS)

    assert result is None


@patch("task_selector.query")
def test_select_task_returns_none_on_empty_list(mock_query):
    result = select_task([])
    assert result is None
    mock_query.assert_not_called()
