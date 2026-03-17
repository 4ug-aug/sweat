def knowledge_blocks(knowledge_dir: str) -> tuple[str, str]:
    """Return (before, after) instruction blocks for knowledge base integration.

    Returns empty strings if knowledge_dir is falsy.
    """
    if not knowledge_dir:
        return "", ""
    before = (
        f"\n0. Before starting, read `{knowledge_dir}/MEMORY.md` to see available "
        "knowledge topics. Then read any files relevant to your current task. "
        "Do not read all files — only what's relevant based on the index.\n"
    )
    after = (
        f"\n6. Before finishing, write a structured entry to the most relevant "
        f"knowledge file(s) in `{knowledge_dir}/`. Use the entry format shown in "
        "MEMORY.md. If you encountered a pitfall or mistake, write to `pitfalls/`. "
        "If you observed a positive pattern, write to `patterns/`. If you learned "
        "something about task types, write to `tasks/`. Keep entries concise and "
        "factual. Only update MEMORY.md if you created a new topic file.\n"
    )
    return before, after
