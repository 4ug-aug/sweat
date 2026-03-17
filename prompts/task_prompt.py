from prompts import knowledge_blocks


def build_agent_prompt(task: dict, repo: str, knowledge_dir: str = "") -> str:
    knowledge_before, knowledge_after = knowledge_blocks(knowledge_dir)

    return f"""You are an AI software engineer working on the repository: {repo}

Your task (Asana GID: {task['gid']}):
**{task['name']}**

Description:
{task.get('notes', 'No description provided.')}

Instructions:
{knowledge_before}1. Explore the repository to understand the codebase relevant to this task.
2. Implement the fix or feature described above.
3. Write or update tests if applicable.
4. Do NOT commit your changes — the orchestrator will handle git.
5. Focus only on this task. Do not refactor unrelated code.
{knowledge_after}
When you are done, summarize what you changed and why in one short paragraph.
"""
