"""Tests for the async wrappers on AsanaClient and GitHubClient."""

from unittest.mock import MagicMock, patch

import pytest


@patch("clients.asana._Client")
async def test_asana_get_unassigned_tasks_async(mock_client_class):
    from clients.asana import AsanaClient

    client = AsanaClient("test-token")
    client.get_unassigned_tasks = MagicMock(return_value=[{"gid": "1"}])

    result = await client.get_unassigned_tasks_async("PROJ")

    client.get_unassigned_tasks.assert_called_once_with("PROJ")
    assert result == [{"gid": "1"}]


@patch("clients.asana._Client")
async def test_asana_assign_task_async(mock_client_class):
    from clients.asana import AsanaClient

    client = AsanaClient("test-token")
    client.assign_task = MagicMock()

    await client.assign_task_async("T1", "U1")

    client.assign_task.assert_called_once_with("T1", "U1")


@patch("clients.asana._Client")
async def test_asana_add_comment_async(mock_client_class):
    from clients.asana import AsanaClient

    client = AsanaClient("test-token")
    client.add_comment = MagicMock()

    await client.add_comment_async("T1", "hello")

    client.add_comment.assert_called_once_with("T1", "hello")


@patch("clients.asana._Client")
async def test_asana_add_time_tracking_entry_async(mock_client_class):
    from clients.asana import AsanaClient

    client = AsanaClient("test-token")
    client.add_time_tracking_entry = MagicMock()

    await client.add_time_tracking_entry_async("T1", 30, "2026-03-13")

    client.add_time_tracking_entry.assert_called_once_with("T1", 30, "2026-03-13")


@patch("clients.github.Github")
async def test_github_clone_repo_async(mock_github_class):
    from clients.github import GitHubClient

    client = GitHubClient("test-token")
    client.clone_repo = MagicMock(return_value="/tmp/repo")

    result = await client.clone_repo_async("org/repo")

    client.clone_repo.assert_called_once_with("org/repo")
    assert result == "/tmp/repo"


@patch("clients.github.Github")
async def test_github_get_bot_login_async(mock_github_class):
    from clients.github import GitHubClient

    client = GitHubClient("test-token")
    client.get_bot_login = MagicMock(return_value="bot-user")

    result = await client.get_bot_login_async()

    client.get_bot_login.assert_called_once()
    assert result == "bot-user"


@patch("clients.github.Github")
async def test_github_get_open_prs_async(mock_github_class):
    from clients.github import GitHubClient

    client = GitHubClient("test-token")
    client.get_open_prs = MagicMock(return_value=[{"number": 1}])

    result = await client.get_open_prs_async("org/repo")

    client.get_open_prs.assert_called_once_with("org/repo")
    assert result == [{"number": 1}]
