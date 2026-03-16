from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.asana import AsanaClient
from clients.github import GitHubClient
from responsibilities.base import ResponsibilityItem
from responsibilities.review_responder import ReviewResponder
from responsibilities.snapshot import PRSnapshot
from responsibilities.state import JsonFileState


def _make_snapshot(prs=None, reviews=None):
    return PRSnapshot(
        prs=prs or [],
        reviews=reviews or {},
        check_status={},
        comment_threads={},
        bot_login="bot",
    )


def _make_state(tmp_path):
    return JsonFileState(path=str(tmp_path / "state.json"))


async def test_check_finds_changes_requested(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        reviews={1: [{"id": 101, "state": "CHANGES_REQUESTED", "body": "fix this"}]},
    )
    state = _make_state(tmp_path)
    responder = ReviewResponder()
    items = await responder.check(snapshot, state)
    assert len(items) == 1
    assert items[0].kind == "review_changes_requested"
    assert items[0].event_key == "org/repo#1:review:101"


async def test_check_skips_handled(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        reviews={1: [{"id": 101, "state": "CHANGES_REQUESTED", "body": "fix this"}]},
    )
    state = _make_state(tmp_path)
    state.mark_handled("org/repo#1:review:101")
    responder = ReviewResponder()
    items = await responder.check(snapshot, state)
    assert len(items) == 0


async def test_check_skips_non_changes_requested(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        reviews={1: [{"id": 101, "state": "APPROVED", "body": "looks good"}]},
    )
    state = _make_state(tmp_path)
    responder = ReviewResponder()
    items = await responder.check(snapshot, state)
    assert len(items) == 0


async def test_execute_success_path(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        reviews={1: [{"id": 101, "state": "CHANGES_REQUESTED", "body": "fix this"}]},
    )
    state = _make_state(tmp_path)
    responder = ReviewResponder()
    await responder.check(snapshot, state)  # sets _state

    item = ResponsibilityItem(
        kind="review_changes_requested",
        repo="org/repo",
        pr_number=1,
        branch="agent/fix",
        event_key="org/repo#1:review:101",
        context={"review_id": 101, "review_body": "fix this"},
    )

    github = MagicMock(spec=GitHubClient)
    github.get_pr_metadata_async = AsyncMock(return_value={"body": "PR body"})
    github.get_pr_diff_async = AsyncMock(return_value="diff content")
    github.get_review_comments_async = AsyncMock(return_value=[])
    github.post_pr_comment_async = AsyncMock()

    from agent import AgentResult
    with patch("responsibilities.review_responder.work_on_branch", new=AsyncMock(return_value=AgentResult(success=True))):
        await responder.execute(item, github, MagicMock(spec=AsanaClient), "agent-1")

    github.post_pr_comment_async.assert_called_once()
    assert state.is_handled("org/repo#1:review:101")
    assert state.get_revision_count("org/repo#PR1") == 1


async def test_execute_max_rounds_exceeded(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        reviews={},
    )
    state = _make_state(tmp_path)
    # Set revision count to max
    for _ in range(3):
        state.increment_revision_count("org/repo#PR1")

    responder = ReviewResponder(max_revision_rounds=3)
    await responder.check(snapshot, state)  # sets _state

    item = ResponsibilityItem(
        kind="review_changes_requested",
        repo="org/repo",
        pr_number=1,
        branch="agent/fix",
        event_key="org/repo#1:review:101",
        context={"review_id": 101, "review_body": "fix this"},
    )

    github = MagicMock(spec=GitHubClient)
    github.post_pr_comment_async = AsyncMock()

    with patch("responsibilities.review_responder.work_on_branch") as mock_work:
        await responder.execute(item, github, MagicMock(spec=AsanaClient), "agent-1")

    mock_work.assert_not_called()
    github.post_pr_comment_async.assert_called_once()
    call_body = github.post_pr_comment_async.call_args[0][2]
    assert "maximum revision rounds" in call_body


async def test_execute_failure_does_not_mark_handled(tmp_path):
    snapshot = _make_snapshot(prs=[], reviews={})
    state = _make_state(tmp_path)
    responder = ReviewResponder()
    await responder.check(snapshot, state)  # sets _state

    item = ResponsibilityItem(
        kind="review_changes_requested",
        repo="org/repo",
        pr_number=1,
        branch="agent/fix",
        event_key="org/repo#1:review:101",
        context={"review_id": 101, "review_body": "fix this"},
    )

    github = MagicMock(spec=GitHubClient)
    github.get_pr_metadata_async = AsyncMock(return_value={"body": "PR body"})
    github.get_pr_diff_async = AsyncMock(return_value="diff")
    github.get_review_comments_async = AsyncMock(return_value=[])
    github.post_pr_comment_async = AsyncMock()

    from agent import AgentResult
    with patch("responsibilities.review_responder.work_on_branch", new=AsyncMock(return_value=AgentResult(success=False, error="agent error"))):
        await responder.execute(item, github, MagicMock(spec=AsanaClient), "agent-1")

    assert not state.is_handled("org/repo#1:review:101")
    github.post_pr_comment_async.assert_called_once()
