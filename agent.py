import logging
import time
from dataclasses import dataclass

from claude_agent_sdk import ClaudeAgentOptions, query

import telemetry
from exceptions import AgentError


@dataclass
class AgentResult:
    success: bool
    summary: str = ""
    error: str | None = None


async def run_agent(repo_path: str | None, prompt: str) -> AgentResult:
    """Run Claude Code SDK headlessly in repo_path with the given prompt."""
    tracer = telemetry.tracer()
    with tracer.start_as_current_span("claude.run_agent") as span:
        if telemetry.claude_calls:
            telemetry.claude_calls.add(1)
        start = time.monotonic()
        try:
            stderr_lines: list[str] = []

            def _capture_stderr(line: str) -> None:
                stderr_lines.append(line)
                logging.warning(f"[claude stderr] {line}")

            options = ClaudeAgentOptions(
                permission_mode="bypassPermissions",
                stderr=_capture_stderr,
                **({"cwd": repo_path} if repo_path else {}),
            )
            summary_parts = []
            async for message in query(prompt=prompt, options=options):
                if hasattr(message, "result") and message.result:
                    summary_parts.append(str(message.result))
            span.set_attribute("claude.success", True)
            return AgentResult(success=True, summary=" ".join(summary_parts))
        except Exception as exc:
            span.set_status(telemetry.trace.StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            stderr_output = "\n".join(stderr_lines)
            if stderr_output:
                logging.error(f"Claude stderr:\n{stderr_output}")
            msg = str(exc)
            if "exit code 1" in msg or "exit code: 1" in msg:
                detail = stderr_output or "no stderr captured"
                raise AgentError(
                    f"Claude CLI exited with code 1: {detail}"
                ) from exc
            raise AgentError(f"Agent failed: {exc}") from exc
        finally:
            if telemetry.claude_call_duration:
                telemetry.claude_call_duration.record(time.monotonic() - start)
