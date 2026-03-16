from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.asana import AsanaClient
from clients.github import GitHubClient
from responsibilities.base import ResponsibilityItem
from responsibilities.comment_responder import CommentResponder
from responsibilities.snapshot import PRSnapshot
from responsibilities.state import JsonFileState


def _make_snapshot(prs=None, comment_threads=None, bot_login="bot"):
    return PRSnapshot(
        prs=prs or [],
        reviews={},
        check_status={},
        comment_threads=comment_threads or {},
        bot_login=bot_login,
    )


def _make_state(tmp_path):
    return JsonFileState(path=str(tmp_path / "state.json"))


def _thread(root_id=1, root_user="user1", replies=None):
    return {
        "root": {"id": root_id, "user_login": root_user, "body": "fix this", "path": "file.py", "line": 10, "created_at": "2024-01-01"},
        "replies": replies or [],
    }


async def test_check_finds_unanswered_thread(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        comment_threads={1: [_thread(root_id=10, root_user="human")]},
    )
    state = _make_state(tmp_path)
    responder = CommentResponder()
    items = await responder.check(snapshot, state)
    assert len(items) == 1
    assert items[0].kind == "pr_comment"
    assert items[0].event_key == "org/repo#1:comment:10"


async def test_check_skips_thread_where_bot_commented_last(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        comment_threads={1: [_thread(
            root_id=10,
            root_user="human",
            replies=[{"id": 11, "user_login": "bot", "body": "done", "path": "f.py", "line": 1, "created_at": "2024-01-02"}],
        )]},
        bot_login="bot",
    )
    state = _make_state(tmp_path)
    responder = CommentResponder()
    items = await responder.check(snapshot, state)
    assert len(items) == 0


async def test_check_skips_handled(tmp_path):
    snapshot = _make_snapshot(
        prs=[{"number": 1, "repo": "org/repo", "head_branch": "agent/fix"}],
        comment_threads={1: [_thread(root_id=10)]},
    )
    state = _make_state(tmp_path)
    state.mark_handled("org/repo#1:comment:10")
    responder = CommentResponder()
    items = await responder.check(snapshot, state)
    assert len(items) == 0


async def test_execute_code_change_path(tmp_path):
    snapshot = _make_snapshot(prs=[], comment_threads={})
    state = _make_state(tmp_path)
    responder = CommentResponder()
    await responder.check(snapshot, state)  # sets _state

    item = ResponsibilityItem(
        kind="pr_comment",
        repo="org/repo",
        pr_number=1,
        branch="agent/fix",
        event_key="org/repo#1:comment:10",
        context={"thread": _thread(root_id=10), "root_comment_id": 10},
    )

    github = MagicMock(spec=GitHubClient)
    github.get_pr_diff_async = AsyncMock(return_value="diff")
    github.get_repo_summary_async = AsyncMock(return_value="summary")
    github.post_pr_comment_async = AsyncMock()
    github.reply_to_pr_comment_async = AsyncMock()

    from agent import AgentResult
    with patch("responsibilities.comment_responder.work_on_branch", new=AsyncMock(return_value=AgentResult(success=True, summary="code changed"))):
        await responder.execute(item, github, MagicMock(spec=AsanaClient), "agent-1")

    github.reply_to_pr_comment_async.assert_called_once()
    assert state.is_handled("org/repo#1:comment:10")
    assert state.get_revision_count("org/repo#PR1") == 1


async def test_execute_reply_path(tmp_path):
    snapshot = _make_snapshot(prs=[], comment_threads={})
    state = _make_state(tmp_path)
    responder = CommentResponder()
    await responder.check(snapshot, state)  # sets _state

    item = ResponsibilityItem(
        kind="pr_comment",
        repo="org/repo",
        pr_number=1,
        branch="agent/fix",
        event_key="org/repo#1:comment:10",
        context={"thread": _thread(root_id=10), "root_comment_id": 10},
    )

    github = MagicMock(spec=GitHubClient)
    github.get_pr_diff_async = AsyncMock(return_value="diff")
    github.get_repo_summary_async = AsyncMock(return_value="summary")
    github.post_pr_comment_async = AsyncMock()
    github.reply_to_pr_comment_async = AsyncMock()

    from agent import AgentResult
    with patch("responsibilities.comment_responder.work_on_branch", new=AsyncMock(return_value=AgentResult(success=True, summary="REPLY: This is intentional because of X"))):
        await responder.execute(item, github, MagicMock(spec=AsanaClient), "agent-1")

    github.reply_to_pr_comment_async.assert_called_once()
    call_body = github.reply_to_pr_comment_async.call_args[0][3]
    assert "This is intentional because of X" in call_body
    assert state.is_handled("org/repo#1:comment:10")
