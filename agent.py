from dataclasses import dataclass
from claude_agent_sdk import query, ClaudeAgentOptions

from exceptions import AgentError


@dataclass
class AgentResult:
    success: bool
    summary: str = ""
    error: str | None = None


async def run_agent(repo_path: str | None, prompt: str) -> AgentResult:
    """Run Claude Code SDK headlessly in repo_path with the given prompt."""
    try:
        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            **({"cwd": repo_path} if repo_path else {}),
        )
        summary_parts = []
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "result") and message.result:
                summary_parts.append(str(message.result))
        return AgentResult(success=True, summary=" ".join(summary_parts))
    except Exception as exc:
        msg = str(exc)
        if "exit code 1" in msg or "exit code: 1" in msg:
            raise AgentError(
                "Claude CLI exited with code 1 — you may need to re-authenticate. "
                "Run `claude` interactively and log in, then retry."
            ) from exc
        raise AgentError(f"Agent failed: {exc}") from exc
