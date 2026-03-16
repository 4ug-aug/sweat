from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.asana import AsanaClient
from clients.github import GitHubClient
from responsibilities.base import ResponsibilityItem
from responsibilities.ci_responder import CIResponder
from responsibilities.snapshot import PRSnapshot
from responsibilities.state import JsonFileState


def _make_snapshot(prs=None, check_status=None):
    return PRSnapshot(
        prs=prs or [],
        reviews={},
        check_status=check_status or {},
        comment_threads={},
        bot_login="bot",
    )


def _make_state(tmp_path):
    return JsonFileState(path=str(tmp_path / "state.json"))


async def test_check_finds_failed_ci(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        check_status={1: "failure"},
    )
    state = _make_state(tmp_path)
    responder = CIResponder()
    items = await responder.check(snapshot, state)
    assert len(items) == 1
    assert items[0].kind == "ci_failure"
    assert items[0].event_key == "org/repo#1:ci_failure"


async def test_check_skips_success(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        check_status={1: "success"},
    )
    state = _make_state(tmp_path)
    responder = CIResponder()
    items = await responder.check(snapshot, state)
    assert len(items) == 0


async def test_check_skips_handled(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        check_status={1: "failure"},
    )
    state = _make_state(tmp_path)
    state.mark_handled("org/repo#1:ci_failure")
    responder = CIResponder()
    items = await responder.check(snapshot, state)
    assert len(items) == 0


async def test_execute_success_path(tmp_path):
    snapshot = _make_snapshot(prs=[], check_status={})
    state = _make_state(tmp_path)
    responder = CIResponder()
    await responder.check(snapshot, state)  # sets _state

    item = ResponsibilityItem(
        kind="ci_failure",
        repo="org/repo",
        pr_number=1,
        branch="agent/fix",
        event_key="org/repo#1:ci_failure",
        context={},
    )

    github = MagicMock(spec=GitHubClient)
    github.get_failed_check_details_async = AsyncMock(return_value=[{"name": "tests", "output": "FAIL"}])
    github.get_pr_diff_async = AsyncMock(return_value="diff")
    github.get_repo_summary_async = AsyncMock(return_value="summary")
    github.post_pr_comment_async = AsyncMock()

    from agent import AgentResult
    with patch("responsibilities.ci_responder.work_on_branch", new=AsyncMock(return_value=AgentResult(success=True))):
        await responder.execute(item, github, MagicMock(spec=AsanaClient), "agent-1")

    github.post_pr_comment_async.assert_called_once()
    assert state.is_handled("org/repo#1:ci_failure")
    assert state.get_revision_count("org/repo#PR1") == 1


async def test_execute_max_rounds_exceeded(tmp_path):
    snapshot = _make_snapshot(prs=[], check_status={})
    state = _make_state(tmp_path)
    for _ in range(3):
        state.increment_revision_count("org/repo#PR1")

    responder = CIResponder(max_revision_rounds=3)
    await responder.check(snapshot, state)  # sets _state

    item = ResponsibilityItem(
        kind="ci_failure",
        repo="org/repo",
        pr_number=1,
        branch="agent/fix",
        event_key="org/repo#1:ci_failure",
        context={},
    )

    github = MagicMock(spec=GitHubClient)
    github.post_pr_comment_async = AsyncMock()

    with patch("responsibilities.ci_responder.work_on_branch") as mock_work:
        await responder.execute(item, github, MagicMock(spec=AsanaClient), "agent-1")

    mock_work.assert_not_called()
    github.post_pr_comment_async.assert_called_once()
    assert "maximum revision rounds" in github.post_pr_comment_async.call_args[0][2]


async def test_execute_failure_does_not_mark_handled(tmp_path):
    snapshot = _make_snapshot(prs=[], check_status={})
    state = _make_state(tmp_path)
    responder = CIResponder()
    await responder.check(snapshot, state)  # sets _state

    item = ResponsibilityItem(
        kind="ci_failure",
        repo="org/repo",
        pr_number=1,
        branch="agent/fix",
        event_key="org/repo#1:ci_failure",
        context={},
    )

    github = MagicMock(spec=GitHubClient)
    github.get_failed_check_details_async = AsyncMock(return_value=[])
    github.get_pr_diff_async = AsyncMock(return_value="diff")
    github.get_repo_summary_async = AsyncMock(return_value="summary")
    github.post_pr_comment_async = AsyncMock()

    from agent import AgentResult
    with patch("responsibilities.ci_responder.work_on_branch", new=AsyncMock(return_value=AgentResult(success=False, error="oops"))):
        await responder.execute(item, github, MagicMock(spec=AsanaClient), "agent-1")

    assert not state.is_handled("org/repo#1:ci_failure")
