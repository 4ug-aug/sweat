import json
import os
import pytest


def test_new_event_not_handled(tmp_path):
    from responsibilities.state import JsonFileState
    state = JsonFileState(path=str(tmp_path / "state.json"))
    assert state.is_handled("org/repo#42:review:1") is False


def test_mark_and_check_handled(tmp_path):
    from responsibilities.state import JsonFileState
    state = JsonFileState(path=str(tmp_path / "state.json"))
    state.mark_handled("org/repo#42:review:1", metadata={"foo": "bar"})
    assert state.is_handled("org/repo#42:review:1") is True


def test_revision_count_starts_zero(tmp_path):
    from responsibilities.state import JsonFileState
    state = JsonFileState(path=str(tmp_path / "state.json"))
    assert state.get_revision_count("org/repo#PR42") == 0


def test_increment_revision_count(tmp_path):
    from responsibilities.state import JsonFileState
    state = JsonFileState(path=str(tmp_path / "state.json"))
    state.increment_revision_count("org/repo#PR42")
    state.increment_revision_count("org/repo#PR42")
    assert state.get_revision_count("org/repo#PR42") == 2


def test_cleanup_removes_closed_prs(tmp_path):
    from responsibilities.state import JsonFileState
    state = JsonFileState(path=str(tmp_path / "state.json"))
    state.mark_handled("org/repo#42:review:1")
    state.mark_handled("org/repo#99:ci_failure")
    state.increment_revision_count("org/repo#PR42")
    state.increment_revision_count("org/repo#PR99")

    # Keep PR 42 open, close PR 99
    state.cleanup({"org/repo#PR42"})

    assert state.is_handled("org/repo#42:review:1") is True
    assert state.is_handled("org/repo#99:ci_failure") is False
    assert state.get_revision_count("org/repo#PR42") == 1
    assert state.get_revision_count("org/repo#PR99") == 0


def test_persistence_across_instances(tmp_path):
    from responsibilities.state import JsonFileState
    path = str(tmp_path / "state.json")
    state1 = JsonFileState(path=path)
    state1.mark_handled("key1")
    state1.increment_revision_count("pr1")

    state2 = JsonFileState(path=path)
    assert state2.is_handled("key1") is True
    assert state2.get_revision_count("pr1") == 1
