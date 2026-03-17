import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent import AgentResult
from agents.code_reviewer import CodeReviewerAgent, _is_duplicate, _parse_findings
from clients.asana import AsanaClient
from clients.github import GitHubClient

_AGENT_CFG = {
    "id": "test-code-reviewer",
    "type": "code_reviewer",
    "projects": [
        {
            "asana_project_id": "PROJECT_123",
            "github_repo": "org/repo",
            "quality_doc_path": "docs/code-quality.md",
        }
    ],
}

_SAMPLE_FINDINGS = json.dumps(
    {
        "findings": [
            {
                "title": "Inconsistent error handling in API layer",
                "category": "inconsistent_pattern",
                "priority": "high",
                "description": "api/handlers.py uses mixed patterns",
                "estimated_minutes": 30,
                "pseudo_solution": "1. Standardize exception handling\n2. Add error middleware",
            },
            {
                "title": "Dead import in utils module",
                "category": "dead_code",
                "priority": "medium",
                "description": "utils/helpers.py:3 imports unused os module",
                "estimated_minutes": 10,
                "pseudo_solution": "1. Remove unused import\n2. Run tests",
            },
            {
                "title": "Complex validation function",
                "category": "complexity",
                "priority": "low",
                "description": "validators.py:45 has cyclomatic complexity of 15",
                "estimated_minutes": 60,
                "pseudo_solution": "1. Split into smaller functions\n2. Write unit tests",
            },
        ]
    }
)


def _make_agent(cfg=None):
    github = MagicMock(spec=GitHubClient)
    asana = MagicMock(spec=AsanaClient)
    github.clone_repo_async = AsyncMock()
    asana.get_tasks_async = AsyncMock()
    asana.create_task_async = AsyncMock()
    return CodeReviewerAgent(
        agent_id="test-code-reviewer",
        config=cfg or _AGENT_CFG,
        github=github,
        asana=asana,
    )


@patch("agents.code_reviewer.run_agent", new_callable=AsyncMock)
@patch("agents.code_reviewer.shutil.rmtree")
async def test_full_flow_creates_3_tasks(mock_rmtree, mock_run_agent, tmp_path):
    agent = _make_agent()
    repo_path = str(tmp_path)
    agent.github.clone_repo_async.return_value = repo_path

    # Create quality doc
    doc_path = tmp_path / "docs" / "code-quality.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("# Quality Standards\nKeep it clean.")

    mock_run_agent.return_value = AgentResult(success=True, summary=_SAMPLE_FINDINGS)
    agent.asana.get_tasks_async.return_value = []

    await agent.run_once()

    assert agent.asana.create_task_async.call_count == 3
    mock_rmtree.assert_called_once_with(repo_path, ignore_errors=True)


@patch("agents.code_reviewer.run_agent", new_callable=AsyncMock)
@patch("agents.code_reviewer.shutil.rmtree")
async def test_skips_when_quality_doc_missing(mock_rmtree, mock_run_agent, tmp_path):
    agent = _make_agent()
    repo_path = str(tmp_path)
    agent.github.clone_repo_async.return_value = repo_path
    # No quality doc created

    await agent.run_once()

    mock_run_agent.assert_not_called()
    agent.asana.create_task_async.assert_not_called()
    mock_rmtree.assert_called_once_with(repo_path, ignore_errors=True)


@patch("agents.code_reviewer.run_agent", new_callable=AsyncMock)
@patch("agents.code_reviewer.shutil.rmtree")
async def test_duplicate_detection_skips_matching(mock_rmtree, mock_run_agent, tmp_path):
    agent = _make_agent()
    repo_path = str(tmp_path)
    agent.github.clone_repo_async.return_value = repo_path

    doc_path = tmp_path / "docs" / "code-quality.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("# Standards")

    mock_run_agent.return_value = AgentResult(success=True, summary=_SAMPLE_FINDINGS)
    # One existing task that matches the first finding
    agent.asana.get_tasks_async.return_value = [
        {"gid": "existing-1", "name": "Inconsistent error handling in API layer"},
    ]

    await agent.run_once()

    assert agent.asana.create_task_async.call_count == 2


@patch("agents.code_reviewer.run_agent", new_callable=AsyncMock)
@patch("agents.code_reviewer.shutil.rmtree")
async def test_agent_failure_no_tasks_created(mock_rmtree, mock_run_agent, tmp_path):
    agent = _make_agent()
    repo_path = str(tmp_path)
    agent.github.clone_repo_async.return_value = repo_path

    doc_path = tmp_path / "docs" / "code-quality.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("# Standards")

    mock_run_agent.return_value = AgentResult(success=False, error="timeout")

    await agent.run_once()

    agent.asana.create_task_async.assert_not_called()


@patch("agents.code_reviewer.run_agent", new_callable=AsyncMock)
@patch("agents.code_reviewer.shutil.rmtree")
async def test_invalid_json_no_crash(mock_rmtree, mock_run_agent, tmp_path):
    agent = _make_agent()
    repo_path = str(tmp_path)
    agent.github.clone_repo_async.return_value = repo_path

    doc_path = tmp_path / "docs" / "code-quality.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("# Standards")

    mock_run_agent.return_value = AgentResult(success=True, summary="not valid json at all")

    await agent.run_once()

    agent.asana.create_task_async.assert_not_called()


@patch("agents.code_reviewer.run_agent", new_callable=AsyncMock)
@patch("agents.code_reviewer.shutil.rmtree")
async def test_cleanup_on_error(mock_rmtree, mock_run_agent, tmp_path):
    agent = _make_agent()
    repo_path = str(tmp_path)
    agent.github.clone_repo_async.return_value = repo_path

    doc_path = tmp_path / "docs" / "code-quality.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("# Standards")

    mock_run_agent.side_effect = Exception("unexpected")

    with pytest.raises(Exception, match="unexpected"):
        await agent.run_once()

    mock_rmtree.assert_called_once_with(repo_path, ignore_errors=True)


# --- Unit tests for helpers ---


def test_parse_findings_plain_json():
    findings = _parse_findings(_SAMPLE_FINDINGS)
    assert len(findings) == 3
    assert findings[0]["title"] == "Inconsistent error handling in API layer"
    assert findings[0]["estimated_minutes"] == 30
    assert "pseudo_solution" in findings[0]


def test_parse_findings_markdown_fenced():
    text = f"```json\n{_SAMPLE_FINDINGS}\n```"
    findings = _parse_findings(text)
    assert len(findings) == 3


def test_parse_findings_empty():
    assert _parse_findings("") == []
    assert _parse_findings("not json") == []


def test_is_duplicate_exact_match():
    assert _is_duplicate("Fix login bug", ["Fix login bug", "Other task"])


def test_is_duplicate_fuzzy_match():
    assert _is_duplicate("Fix the login bug", ["Fix login bug", "Other task"])


def test_is_duplicate_no_match():
    assert not _is_duplicate("Completely different task", ["Fix login bug", "Other task"])
