import json
import logging

from claude_agent_sdk import ClaudeAgentOptions, query

_SYSTEM = """You are an AI agent that evaluates software tasks for feasibility.
Given a list of tasks and context about the codebase, you pick the ONE task you are
most confident you can implement in code. Use the repo context to assess whether the
codebase has the right structure, language, and patterns for you to tackle the task.
Prefer tasks with clear bug descriptions, specific acceptance criteria, or small scope.
Avoid tasks that are vague, require human judgment, or are non-technical.

Respond ONLY with valid JSON in this format:
{"task_gid": "<gid or null>", "reason": "<one sentence>"}"""


async def select_task(tasks: list[dict], repo_context: str = "") -> dict | None:
    if not tasks:
        return None
    task_list = "\n".join(
        f"- GID: {t['gid']} | Name: {t['name']} | Notes: {t.get('notes', '')[:200]}"
        for t in tasks
    )
    context_section = f"\n\n## Codebase context\n{repo_context}" if repo_context else ""
    prompt = f"{_SYSTEM}{context_section}\n\nHere are the available tasks:\n\n{task_list}\n\nWhich one should I work on? Reply with JSON only."

    text = ""
    async for message in query(prompt=prompt, options=ClaudeAgentOptions()):
        if hasattr(message, "content"):
            for block in message.content:
                if hasattr(block, "text"):
                    text = block.text

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
