import json
import os

import pytest

import audit
import config


@pytest.fixture(autouse=True)
def tmp_audit_log(tmp_path, monkeypatch):
    log_path = str(tmp_path / "audit.jsonl")
    monkeypatch.setattr(config, "AUDIT_LOG_PATH", log_path)
    return log_path


def test_log_event_creates_file(tmp_audit_log):
    assert not os.path.exists(tmp_audit_log)
    audit.log_event("test_event")
    assert os.path.exists(tmp_audit_log)


def test_log_event_writes_correct_fields(tmp_audit_log):
    audit.log_event("task_selected", task_gid="123", task_name="Fix bug", repo="org/repo")
    with open(tmp_audit_log) as f:
        record = json.loads(f.readline())
    assert record["event"] == "task_selected"
    assert record["task_gid"] == "123"
    assert record["task_name"] == "Fix bug"
    assert record["repo"] == "org/repo"
    assert "timestamp" in record


def test_log_event_appends(tmp_audit_log):
    audit.log_event("first_event")
    audit.log_event("second_event")
    with open(tmp_audit_log) as f:
        lines = [l.strip() for l in f if l.strip()]
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "first_event"
    assert json.loads(lines[1])["event"] == "second_event"


def test_log_event_includes_agent_id(tmp_audit_log):
    audit.log_event("task_selected", agent_id="impl-1", task_gid="123")
    with open(tmp_audit_log) as f:
        record = json.loads(f.readline())
    assert record["agent_id"] == "impl-1"


def test_log_event_omits_agent_id_when_none(tmp_audit_log):
    audit.log_event("test_event")
    with open(tmp_audit_log) as f:
        record = json.loads(f.readline())
    assert "agent_id" not in record
