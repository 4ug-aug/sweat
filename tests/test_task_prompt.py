from prompts.task_prompt import build_agent_prompt


def test_prompt_includes_task_name():
    task = {"gid": "111", "name": "Fix login bug", "notes": "Users can't log in"}
    prompt = build_agent_prompt(task, "augusttollerup/myrepo")
    assert "Fix login bug" in prompt


def test_prompt_includes_task_notes():
    task = {"gid": "111", "name": "Fix login bug", "notes": "Users can't log in via /api/auth"}
    prompt = build_agent_prompt(task, "augusttollerup/myrepo")
    assert "Users can't log in via /api/auth" in prompt


def test_prompt_includes_repo():
    task = {"gid": "111", "name": "Fix login bug", "notes": ""}
    prompt = build_agent_prompt(task, "augusttollerup/myrepo")
    assert "augusttollerup/myrepo" in prompt


def test_prompt_includes_asana_task_id():
    task = {"gid": "111", "name": "Fix login bug", "notes": ""}
    prompt = build_agent_prompt(task, "augusttollerup/myrepo")
    assert "111" in prompt


def test_prompt_instructs_commit():
    task = {"gid": "111", "name": "Fix login bug", "notes": ""}
    prompt = build_agent_prompt(task, "augusttollerup/myrepo")
    assert "commit" in prompt.lower()
