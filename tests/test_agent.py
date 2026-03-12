import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from agent import run_agent, AgentResult


@pytest.mark.asyncio
@patch("agent.query")
async def test_run_agent_returns_success(mock_query):
    async def fake_messages():
        result = MagicMock()
        result.__class__.__name__ = "ResultMessage"
        result.subtype = "success"
        yield result

    mock_query.return_value = fake_messages()

    result = await run_agent("/tmp/somerepo", "Fix the login bug in auth.py")

    assert result.success is True
    mock_query.assert_called_once()
    call_kwargs = mock_query.call_args
    assert call_kwargs.kwargs["prompt"] == "Fix the login bug in auth.py"


@pytest.mark.asyncio
@patch("agent.query")
async def test_run_agent_returns_failure_on_error(mock_query):
    mock_query.side_effect = Exception("Claude timed out")

    result = await run_agent("/tmp/somerepo", "Fix something")

    assert result.success is False
    assert "Claude timed out" in result.error
