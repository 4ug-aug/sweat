import json
from pathlib import Path

from dashboard import state as agent_state


def test_write_creates_file(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sweat"
    state_file = state_dir / "agent_states.json"
    monkeypatch.setattr(agent_state, "STATE_DIR", state_dir)
    monkeypatch.setattr(agent_state, "STATE_FILE", state_file)

    agent_state.write_agent_state("agent-1", "idle", "implementer")

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert "agent-1" in data
    entry = data["agent-1"]
    assert entry["status"] == "idle"
    assert entry["loop_name"] == "implementer"
    assert "last_run" in entry
    assert entry["last_error"] is None


def test_write_preserves_other_agents(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sweat"
    state_file = state_dir / "agent_states.json"
    monkeypatch.setattr(agent_state, "STATE_DIR", state_dir)
    monkeypatch.setattr(agent_state, "STATE_FILE", state_file)

    agent_state.write_agent_state("agent-1", "idle", "implementer")
    agent_state.write_agent_state("agent-2", "running", "reviewer")

    data = json.loads(state_file.read_text())
    assert "agent-1" in data
    assert "agent-2" in data
    assert data["agent-1"]["loop_name"] == "implementer"
    assert data["agent-2"]["loop_name"] == "reviewer"


def test_write_overwrites_same_agent(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sweat"
    state_file = state_dir / "agent_states.json"
    monkeypatch.setattr(agent_state, "STATE_DIR", state_dir)
    monkeypatch.setattr(agent_state, "STATE_FILE", state_file)

    agent_state.write_agent_state("agent-1", "idle", "implementer")
    agent_state.write_agent_state("agent-1", "running", "implementer")

    data = json.loads(state_file.read_text())
    assert len(data) == 1
    assert data["agent-1"]["status"] == "running"


def test_read_returns_empty_on_missing_file(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sweat"
    state_file = state_dir / "agent_states.json"
    monkeypatch.setattr(agent_state, "STATE_DIR", state_dir)
    monkeypatch.setattr(agent_state, "STATE_FILE", state_file)

    result = agent_state.read_all_states()

    assert result == {}


def test_read_returns_empty_on_corrupt_file(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sweat"
    state_dir.mkdir()
    state_file = state_dir / "agent_states.json"
    state_file.write_text("not valid json {{{{")
    monkeypatch.setattr(agent_state, "STATE_DIR", state_dir)
    monkeypatch.setattr(agent_state, "STATE_FILE", state_file)

    result = agent_state.read_all_states()

    assert result == {}


def test_write_with_error(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sweat"
    state_file = state_dir / "agent_states.json"
    monkeypatch.setattr(agent_state, "STATE_DIR", state_dir)
    monkeypatch.setattr(agent_state, "STATE_FILE", state_file)

    agent_state.write_agent_state("agent-1", "error", "implementer", last_error="boom")

    data = json.loads(state_file.read_text())
    assert data["agent-1"]["last_error"] == "boom"
