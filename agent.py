from dataclasses import dataclass
from claude_agent_sdk import query, ClaudeAgentOptions


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
        return AgentResult(success=False, error=str(exc))
