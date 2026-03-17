import json
from pathlib import Path
from unittest.mock import MagicMock

from starlette.testclient import TestClient

from clients.github import GitHubClient
import dashboard.server as dashboard_mod


def test_agents_endpoint_merges_config_and_state(monkeypatch):
    monkeypatch.setattr("config.AGENTS", [
        {
            "id": "impl-1",
            "type": "implementer",
            "interval": 60,
            "projects": [{"github_repo": "org/repo1"}],
        }
    ])
    monkeypatch.setattr("dashboard.server.read_all_states", lambda: {
        "impl-1": {
            "status": "idle",
            "loop_name": "loop-0",
            "last_run": "2026-03-17T00:00:00Z",
            "last_error": None,
        }
    })
    client = TestClient(dashboard_mod.app)
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    agent = data[0]
    assert agent["id"] == "impl-1"
    assert agent["status"] == "idle"
    assert agent["repos"] == ["org/repo1"]
    assert agent["type"] == "implementer"
    assert agent["interval"] == 60
    assert agent["loop_name"] == "loop-0"


def test_agents_unknown_status_when_no_state(monkeypatch):
    monkeypatch.setattr("config.AGENTS", [
        {"id": "rev-1", "type": "reviewer", "projects": []},
    ])
    monkeypatch.setattr("dashboard.server.read_all_states", lambda: {})
    client = TestClient(dashboard_mod.app)
    resp = client.get("/api/agents")
    data = resp.json()
    assert data[0]["status"] == "unknown"
    assert data[0]["last_run"] is None


def test_log_endpoint_returns_entries(monkeypatch, tmp_path):
    log_file = tmp_path / "audit.jsonl"
    log_file.write_text(
        json.dumps({"ts": "1", "msg": "first"}) + "\n"
        + json.dumps({"ts": "2", "msg": "second"}) + "\n"
    )
    monkeypatch.setattr("config.AUDIT_LOG_PATH", str(log_file))
    monkeypatch.setattr("config.AGENTS", [])
    client = TestClient(dashboard_mod.app)
    resp = client.get("/api/log")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["msg"] == "second"  # reverse chronological


def test_log_endpoint_empty_returns_empty_list(monkeypatch, tmp_path):
    monkeypatch.setattr("config.AUDIT_LOG_PATH", str(tmp_path / "nonexistent.jsonl"))
    monkeypatch.setattr("config.AGENTS", [])
    client = TestClient(dashboard_mod.app)
    resp = client.get("/api/log")
    assert resp.status_code == 200
    assert resp.json() == []


def test_log_endpoint_respects_last_param(monkeypatch, tmp_path):
    log_file = tmp_path / "audit.jsonl"
    lines = [json.dumps({"i": i}) for i in range(10)]
    log_file.write_text("\n".join(lines) + "\n")
    monkeypatch.setattr("config.AUDIT_LOG_PATH", str(log_file))
    monkeypatch.setattr("config.AGENTS", [])
    client = TestClient(dashboard_mod.app)
    resp = client.get("/api/log?last=3")
    data = resp.json()
    assert len(data) == 3


def test_log_entries_reverse_chronological(monkeypatch, tmp_path):
    log_file = tmp_path / "audit.jsonl"
    lines = [json.dumps({"i": i}) for i in range(5)]
    log_file.write_text("\n".join(lines) + "\n")
    monkeypatch.setattr("config.AUDIT_LOG_PATH", str(log_file))
    monkeypatch.setattr("config.AGENTS", [])
    client = TestClient(dashboard_mod.app)
    resp = client.get("/api/log")
    data = resp.json()
    # Most recent (last in file) should be first in response
    assert data[0]["i"] == 4
    assert data[-1]["i"] == 0


def test_prs_endpoint(monkeypatch):
    monkeypatch.setattr("config.AGENTS", [
        {
            "id": "impl-1",
            "type": "implementer",
            "projects": [{"github_repo": "org/repo1"}],
        }
    ])
    mock_gh = MagicMock(spec=GitHubClient)
    mock_gh.get_open_prs.return_value = [
        {
            "number": 42,
            "title": "Add feature",
            "author_login": "bot",
            "head_branch": "feat-branch",
            "base_branch": "main",
            "html_url": "https://github.com/org/repo1/pull/42",
        }
    ]
    mock_gh.get_pr_check_status.return_value = "success"
    mock_gh.get_pr_reviews.return_value = [
        {"id": 1, "user_login": "reviewer", "state": "APPROVED", "body": "LGTM", "submitted_at": None}
    ]

    monkeypatch.setattr(dashboard_mod, "_build_github_client", lambda: mock_gh)
    client = TestClient(dashboard_mod.app)
    resp = client.get("/api/prs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    pr = data[0]
    assert pr["number"] == 42
    assert pr["repo"] == "org/repo1"
    assert pr["check_status"] == "success"
    assert len(pr["reviews"]) == 1


def test_prs_endpoint_no_credentials(monkeypatch):
    monkeypatch.setattr("config.AGENTS", [])
    monkeypatch.setattr(dashboard_mod, "_build_github_client", lambda: None)
    client = TestClient(dashboard_mod.app)
    resp = client.get("/api/prs")
    assert resp.status_code == 500
    assert "error" in resp.json()


def test_index_returns_html(monkeypatch, tmp_path):
    html_file = tmp_path / "dashboard.html"
    html_file.write_text("<html><body>Hello</body></html>")
    monkeypatch.setattr("config.AGENTS", [])
    monkeypatch.setattr(dashboard_mod, "DASHBOARD_HTML", html_file)
    client = TestClient(dashboard_mod.app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
