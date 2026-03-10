import asyncio
import json
from claude_agent_sdk import query, ClaudeAgentOptions

_SYSTEM = """You are an AI agent that evaluates software tasks for feasibility.
Given a list of tasks, you pick the ONE task you are most confident you can implement
in code. Prefer tasks with clear bug descriptions, specific acceptance criteria, or
small scope. Avoid tasks that are vague, require human judgment, or are non-technical.

Respond ONLY with valid JSON in this format:
{"task_gid": "<gid or null>", "reason": "<one sentence>"}"""


async def _select(tasks: list[dict]) -> dict | None:
    task_list = "\n".join(
        f"- GID: {t['gid']} | Name: {t['name']} | Notes: {t.get('notes', '')[:200]}"
        for t in tasks
    )
    prompt = f"{_SYSTEM}\n\nHere are the available tasks:\n\n{task_list}\n\nWhich one should I work on? Reply with JSON only."

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
        return None
    selected_gid = data.get("task_gid")
    if not selected_gid:
        return None

    return next((t for t in tasks if t["gid"] == selected_gid), None)


def select_task(tasks: list[dict]) -> dict | None:
    if not tasks:
        return None
    return asyncio.run(_select(tasks))
