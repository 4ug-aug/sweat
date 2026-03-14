def build_agent_prompt(task: dict, repo: str, knowledge_dir: str = "") -> str:
    knowledge_before = ""
    knowledge_after = ""
    if knowledge_dir:
        knowledge_before = f"""
0. Before starting, read `{knowledge_dir}/MEMORY.md` to see available knowledge topics. Then read any files relevant to your current task. Do not read all files — only what's relevant based on the index.
"""
        knowledge_after = f"""
6. Before finishing, write a structured entry to the most relevant knowledge file(s) in `{knowledge_dir}/`. Use the entry format shown in MEMORY.md. If you encountered a pitfall or mistake, write to `pitfalls/`. If you observed a positive pattern, write to `patterns/`. If you learned something about task types, write to `tasks/`. Keep entries concise and factual. Only update MEMORY.md if you created a new topic file.
"""

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
