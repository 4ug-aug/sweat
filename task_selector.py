import json
import logging
import time

from claude_agent_sdk import ClaudeAgentOptions, query

import telemetry
from exceptions import TaskSelectorError

_SYSTEM = """You are an AI agent that evaluates software tasks for feasibility.
Given a list of tasks and context about the codebase, you pick the ONE task you are
most confident you can implement in code. Use the repo context to assess whether the
codebase has the right structure, language, and patterns for you to tackle the task.
Prefer tasks with clear bug descriptions, specific acceptance criteria, or small scope.
Avoid tasks that are vague, require human judgment, or are non-technical.

Respond ONLY with valid JSON in this format:
{"task_gid": "<gid or null>", "reason": "<one sentence>"}"""


def _format_task_line(task: dict) -> str:
    def _cf(name):
        for cf in task.get("custom_fields", []):
            if cf.get("name") == name:
                return cf.get("display_value") or ""
        return ""

    meta_parts = []
    for label, field in [("Priority", "Priority"), ("Est", "Estimated Time"),
                          ("Type", "Work Type"), ("Domain", "Domain")]:
        val = _cf(field)
        if val:
            meta_parts.append(f"{label}: {val}")
    meta = " | ".join(meta_parts)
    meta_str = f" | {meta}" if meta else ""
    notes = task.get("notes", "")[:200]
    return f"- GID: {task['gid']} | Name: {task['name']}{meta_str} | Notes: {notes}"


async def select_task(tasks: list[dict], repo_context: str = "") -> dict | None:
    if not tasks:
        return None
    task_list = "\n".join(_format_task_line(t) for t in tasks)
    context_section = f"\n\n## Codebase context\n{repo_context}" if repo_context else ""
    prompt = f"{_SYSTEM}{context_section}\n\nHere are the available tasks:\n\n{task_list}\n\nWhich one should I work on? Reply with JSON only."

    tracer = telemetry.tracer()
    with tracer.start_as_current_span("claude.select_task", attributes={"tasks.count": len(tasks)}) as span:
        if telemetry.claude_calls:
            telemetry.claude_calls.add(1)
        start = time.monotonic()
        text = ""
        try:
            async for message in query(prompt=prompt, options=ClaudeAgentOptions(
                permission_mode="bypassPermissions",
                stderr=lambda line: logging.warning(f"[claude stderr] {line}"),
            )):
                if hasattr(message, "content"):
                    for block in message.content:
                        if hasattr(block, "text"):
                            text = block.text
        except Exception as exc:
            span.set_status(telemetry.trace.StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            msg = str(exc)
            if "exit code 1" in msg or "exit code: 1" in msg:
                raise TaskSelectorError(
                    "Claude CLI exited with code 1 — you may need to re-authenticate. "
                    "Run `claude` interactively and log in, then retry."
                ) from exc
            raise TaskSelectorError(f"Claude agent failed during task selection: {exc}") from exc
        finally:
            if telemetry.claude_call_duration:
                telemetry.claude_call_duration.record(time.monotonic() - start)

    if not text:
        return None

    # Extract JSON — Claude may wrap it in markdown fences
    if "```" in text:
        text = text.split("```")[1]
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logging.error(f"Task selector: failed to parse JSON: {text}")
        return None
    selected_gid = data.get("task_gid")
    if not selected_gid:
        logging.error(f"Task selector: no task GID found in: {data}")
        return None
    logging.info(
        f"Task selector: selected task: {selected_gid}, reason: {data.get('reason')}"
    )
    return next((t for t in tasks if t["gid"] == selected_gid), None)
