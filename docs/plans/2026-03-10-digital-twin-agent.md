# Digital Twin Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a scheduled Python agent that picks a feasible Asana task, takes ownership, proposes a solution, implements it via Claude Code SDK, and opens a GitHub PR.

**Architecture:** A single Python process runs on cron, calls Asana to find an unassigned task, asks Claude to pick the most feasible one, clones the target repo to a temp dir, runs the Claude Code SDK (headless) to implement the fix, then pushes a branch and opens a PR. All external calls (Asana, Anthropic, GitHub, git) are behind thin interfaces so tests can mock them.

**Tech Stack:** Python 3.11+, `anthropic` (task selection), `claude-agent-sdk` (code implementation), `asana` (Asana REST client), `PyGithub` (PR creation), `GitPython` (clone/push), `python-dotenv`, `pytest`, `pytest-asyncio`

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.py`
- Create: `tests/__init__.py`
- Create: `prompts/__init__.py`

**Step 1: Create `requirements.txt`**

```
anthropic>=0.40.0
claude-agent-sdk>=0.0.14
asana>=5.0.0
PyGithub>=2.1.1
GitPython>=3.1.41
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

**Step 2: Create `.env.example`**

```bash
ANTHROPIC_API_KEY=your_key_here
ASANA_TOKEN=your_token_here
GITHUB_TOKEN=your_token_here
ASANA_ASSIGNEE_GID=your_user_gid_here
```

**Step 3: Create `config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ASANA_TOKEN = os.environ["ASANA_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ASANA_ASSIGNEE_GID = os.environ["ASANA_ASSIGNEE_GID"]

# Map Asana project GIDs to GitHub repos
PROJECTS = [
    {
        "asana_project_id": "YOUR_PROJECT_GID",
        "github_repo": "augusttollerup/your-repo",
        "branch_prefix": "agent/",
    }
]
```

**Step 4: Create empty `tests/__init__.py` and `prompts/__init__.py`**

```bash
touch tests/__init__.py prompts/__init__.py
```

**Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 6: Commit**

```bash
git add requirements.txt .env.example config.py tests/__init__.py prompts/__init__.py
git commit -m "feat: project scaffolding"
```

---

## Task 2: Asana Client

**Files:**
- Create: `asana_client.py`
- Create: `tests/test_asana_client.py`

**Step 1: Write the failing tests**

```python
# tests/test_asana_client.py
from unittest.mock import MagicMock, patch
import pytest
from asana_client import get_unassigned_tasks, assign_task, add_comment


@patch("asana_client.asana.Client")
def test_get_unassigned_tasks_returns_list(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.access_token.return_value = mock_client
    mock_client.tasks.get_tasks_for_project.return_value = [
        {"gid": "111", "name": "Fix login bug", "notes": "Users can't log in"},
        {"gid": "222", "name": "Add dark mode", "notes": ""},
    ]
    mock_client.tasks.get_task.side_effect = lambda gid, **_: {
        "gid": gid,
        "name": "Fix login bug" if gid == "111" else "Add dark mode",
        "notes": "Users can't log in" if gid == "111" else "",
        "assignee": None,
    }

    tasks = get_unassigned_tasks("PROJECT_GID")

    assert len(tasks) == 2
    assert tasks[0]["gid"] == "111"
    assert tasks[0]["assignee"] is None


@patch("asana_client.asana.Client")
def test_get_unassigned_tasks_filters_assigned(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.access_token.return_value = mock_client
    mock_client.tasks.get_tasks_for_project.return_value = [
        {"gid": "111", "name": "Fix login bug"},
    ]
    mock_client.tasks.get_task.return_value = {
        "gid": "111",
        "name": "Fix login bug",
        "notes": "",
        "assignee": {"gid": "someone"},
    }

    tasks = get_unassigned_tasks("PROJECT_GID")

    assert tasks == []


@patch("asana_client.asana.Client")
def test_assign_task_calls_api(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.access_token.return_value = mock_client

    assign_task("TASK_GID", "USER_GID")

    mock_client.tasks.update_task.assert_called_once_with(
        "TASK_GID", {"assignee": "USER_GID"}, opt_pretty=True
    )


@patch("asana_client.asana.Client")
def test_add_comment_calls_api(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.access_token.return_value = mock_client

    add_comment("TASK_GID", "Hello from agent")

    mock_client.stories.create_story_for_task.assert_called_once_with(
        "TASK_GID", {"text": "Hello from agent"}, opt_pretty=True
    )
```

**Step 2: Run to verify tests fail**

```bash
pytest tests/test_asana_client.py -v
```
Expected: ImportError — `asana_client` not found

**Step 3: Write `asana_client.py`**

```python
import asana
import config


def _client() -> asana.Client:
    return asana.Client.access_token(config.ASANA_TOKEN)


def get_unassigned_tasks(project_id: str) -> list[dict]:
    client = _client()
    task_refs = client.tasks.get_tasks_for_project(
        project_id,
        opt_fields="gid,name",
        opt_pretty=True,
    )
    tasks = []
    for ref in task_refs:
        task = client.tasks.get_task(ref["gid"], opt_fields="gid,name,notes,assignee")
        if task.get("assignee") is None:
            tasks.append(task)
    return tasks


def assign_task(task_id: str, user_gid: str) -> None:
    client = _client()
    client.tasks.update_task(task_id, {"assignee": user_gid}, opt_pretty=True)


def add_comment(task_id: str, text: str) -> None:
    client = _client()
    client.stories.create_story_for_task(task_id, {"text": text}, opt_pretty=True)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_asana_client.py -v
```
Expected: 4 passed

**Step 5: Commit**

```bash
git add asana_client.py tests/test_asana_client.py
git commit -m "feat: asana client"
```

---

## Task 3: Task Selector

**Files:**
- Create: `task_selector.py`
- Create: `tests/test_task_selector.py`

**Step 1: Write the failing tests**

```python
# tests/test_task_selector.py
from unittest.mock import MagicMock, patch
import pytest
from task_selector import select_task

TASKS = [
    {"gid": "111", "name": "Fix login bug", "notes": "Users can't log in on /api/auth"},
    {"gid": "222", "name": "Add dark mode", "notes": ""},
    {"gid": "333", "name": "Write Q3 roadmap", "notes": "Business planning doc"},
]


@patch("task_selector.anthropic.Anthropic")
def test_select_task_returns_task_when_feasible(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"task_gid": "111", "reason": "Clear bug with reproduction"}')]
    )

    result = select_task(TASKS)

    assert result is not None
    assert result["gid"] == "111"


@patch("task_selector.anthropic.Anthropic")
def test_select_task_returns_none_when_no_feasible_task(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"task_gid": null, "reason": "All tasks are too vague"}')]
    )

    result = select_task(TASKS)

    assert result is None


@patch("task_selector.anthropic.Anthropic")
def test_select_task_returns_none_on_empty_list(mock_anthropic_class):
    result = select_task([])
    assert result is None
```

**Step 2: Run to verify tests fail**

```bash
pytest tests/test_task_selector.py -v
```
Expected: ImportError

**Step 3: Write `task_selector.py`**

```python
import json
import anthropic
import config

_SYSTEM = """You are an AI agent that evaluates software tasks for feasibility.
Given a list of tasks, you pick the ONE task you are most confident you can implement
in code. Prefer tasks with clear bug descriptions, specific acceptance criteria, or
small scope. Avoid tasks that are vague, require human judgment, or are non-technical.

Respond ONLY with valid JSON in this format:
{"task_gid": "<gid or null>", "reason": "<one sentence>"}"""


def select_task(tasks: list[dict]) -> dict | None:
    if not tasks:
        return None

    task_list = "\n".join(
        f"- GID: {t['gid']} | Name: {t['name']} | Notes: {t.get('notes', '')[:200]}"
        for t in tasks
    )
    prompt = f"Here are the available tasks:\n\n{task_list}\n\nWhich one should I work on?"

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=256,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    data = json.loads(response.content[0].text)
    selected_gid = data.get("task_gid")

    if not selected_gid:
        return None

    return next((t for t in tasks if t["gid"] == selected_gid), None)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_task_selector.py -v
```
Expected: 3 passed

**Step 5: Commit**

```bash
git add task_selector.py tests/test_task_selector.py
git commit -m "feat: task selector using claude"
```

---

## Task 4: GitHub Client

**Files:**
- Create: `github_client.py`
- Create: `tests/test_github_client.py`

**Step 1: Write the failing tests**

```python
# tests/test_github_client.py
import os
import tempfile
from unittest.mock import MagicMock, patch, call
import pytest
from github_client import clone_repo, create_branch, commit_and_push, create_pr


@patch("github_client.git.Repo.clone_from")
def test_clone_repo_returns_path(mock_clone):
    mock_clone.return_value = MagicMock()
    path = clone_repo("augusttollerup/myrepo")
    assert os.path.isabs(path)
    assert mock_clone.called
    url = mock_clone.call_args[0][0]
    assert "augusttollerup/myrepo" in url


@patch("github_client.git.Repo")
def test_create_branch(mock_repo_class):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    create_branch("/tmp/somerepo", "agent/asana-111-fix-login")

    mock_repo.git.checkout.assert_called_once_with("-b", "agent/asana-111-fix-login")


@patch("github_client.git.Repo")
def test_commit_and_push(mock_repo_class):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    commit_and_push("/tmp/somerepo", "agent/asana-111-fix-login", "fix: resolve login bug")

    mock_repo.git.add.assert_called_once_with("--all")
    mock_repo.index.commit.assert_called_once_with("fix: resolve login bug")
    mock_repo.git.push.assert_called_once_with("--set-upstream", "origin", "agent/asana-111-fix-login")


@patch("github_client.Github")
def test_create_pr_returns_url(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    mock_pr = MagicMock()
    mock_pr.html_url = "https://github.com/augusttollerup/myrepo/pull/42"
    mock_repo.create_pull.return_value = mock_pr

    url = create_pr(
        repo="augusttollerup/myrepo",
        branch="agent/asana-111-fix-login",
        title="fix: resolve login bug",
        body="Fixes Asana task #111",
    )

    assert url == "https://github.com/augusttollerup/myrepo/pull/42"
    mock_repo.create_pull.assert_called_once_with(
        title="fix: resolve login bug",
        body="Fixes Asana task #111",
        head="agent/asana-111-fix-login",
        base="main",
    )
```

**Step 2: Run to verify tests fail**

```bash
pytest tests/test_github_client.py -v
```
Expected: ImportError

**Step 3: Write `github_client.py`**

```python
import tempfile
import git
from github import Github
import config


def clone_repo(repo: str) -> str:
    """Clone repo to a fresh temp dir, return the path."""
    tmp = tempfile.mkdtemp(prefix="sweat_")
    url = f"https://x-access-token:{config.GITHUB_TOKEN}@github.com/{repo}.git"
    git.Repo.clone_from(url, tmp)
    return tmp


def create_branch(repo_path: str, branch_name: str) -> None:
    repo = git.Repo(repo_path)
    repo.git.checkout("-b", branch_name)


def commit_and_push(repo_path: str, branch_name: str, message: str) -> None:
    repo = git.Repo(repo_path)
    repo.git.add("--all")
    repo.index.commit(message)
    repo.git.push("--set-upstream", "origin", branch_name)


def create_pr(repo: str, branch: str, title: str, body: str) -> str:
    """Open a PR and return its URL."""
    gh = Github(config.GITHUB_TOKEN)
    gh_repo = gh.get_repo(repo)
    pr = gh_repo.create_pull(title=title, body=body, head=branch, base="main")
    return pr.html_url
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_github_client.py -v
```
Expected: 4 passed

**Step 5: Commit**

```bash
git add github_client.py tests/test_github_client.py
git commit -m "feat: github client"
```

---

## Task 5: Agent Interface

**Files:**
- Create: `agent.py`
- Create: `tests/test_agent.py`

**Step 1: Write the failing tests**

```python
# tests/test_agent.py
import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from agent import run_agent, AgentResult


@pytest.mark.asyncio
@patch("agent.query")
async def test_run_agent_returns_success(mock_query):
    async def fake_messages():
        result = MagicMock()
        result.__class__.__name__ = "ResultMessage"
        result.subtype = "success"
        yield result

    mock_query.return_value = fake_messages()

    result = await run_agent("/tmp/somerepo", "Fix the login bug in auth.py")

    assert result.success is True
    mock_query.assert_called_once()
    call_kwargs = mock_query.call_args
    assert call_kwargs.kwargs["prompt"] == "Fix the login bug in auth.py"


@pytest.mark.asyncio
@patch("agent.query")
async def test_run_agent_returns_failure_on_error(mock_query):
    mock_query.side_effect = Exception("Claude timed out")

    result = await run_agent("/tmp/somerepo", "Fix something")

    assert result.success is False
    assert "Claude timed out" in result.error
```

**Step 2: Run to verify tests fail**

```bash
pytest tests/test_agent.py -v
```
Expected: ImportError

**Step 3: Write `agent.py`**

```python
from dataclasses import dataclass, field
from claude_agent_sdk import query, ClaudeAgentOptions


@dataclass
class AgentResult:
    success: bool
    summary: str = ""
    error: str | None = None


async def run_agent(repo_path: str, prompt: str) -> AgentResult:
    """Run Claude Code SDK headlessly in repo_path with the given prompt."""
    try:
        options = ClaudeAgentOptions(
            cwd=repo_path,
            permission_mode="acceptEdits",
        )
        summary_parts = []
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "result") and message.result:
                summary_parts.append(str(message.result))
        return AgentResult(success=True, summary=" ".join(summary_parts))
    except Exception as exc:
        return AgentResult(success=False, error=str(exc))
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_agent.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add agent.py tests/test_agent.py
git commit -m "feat: claude code sdk agent interface"
```

---

## Task 6: Prompt Builder

**Files:**
- Create: `prompts/task_prompt.py`
- Create: `tests/test_task_prompt.py`

**Step 1: Write the failing tests**

```python
# tests/test_task_prompt.py
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
```

**Step 2: Run to verify tests fail**

```bash
pytest tests/test_task_prompt.py -v
```
Expected: ImportError

**Step 3: Write `prompts/task_prompt.py`**

```python
def build_agent_prompt(task: dict, repo: str) -> str:
    return f"""You are an AI software engineer working on the repository: {repo}

Your task (Asana GID: {task['gid']}):
**{task['name']}**

Description:
{task.get('notes', 'No description provided.')}

Instructions:
1. Explore the repository to understand the codebase relevant to this task.
2. Implement the fix or feature described above.
3. Write or update tests if applicable.
4. Do NOT commit your changes — the orchestrator will handle git.
5. Focus only on this task. Do not refactor unrelated code.

When you are done, summarize what you changed and why in one short paragraph.
"""
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_task_prompt.py -v
```
Expected: 5 passed

**Step 5: Commit**

```bash
git add prompts/task_prompt.py tests/test_task_prompt.py
git commit -m "feat: agent prompt builder"
```

---

## Task 7: Main Orchestrator

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

**Step 1: Write the failing tests**

```python
# tests/test_main.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest
from main import run


@pytest.mark.asyncio
@patch("main.add_comment")
@patch("main.create_pr")
@patch("main.commit_and_push")
@patch("main.create_branch")
@patch("main.run_agent")
@patch("main.clone_repo")
@patch("main.assign_task")
@patch("main.select_task")
@patch("main.get_unassigned_tasks")
async def test_run_full_flow(
    mock_get_tasks, mock_select, mock_assign,
    mock_clone, mock_run_agent, mock_create_branch,
    mock_commit_push, mock_create_pr, mock_add_comment
):
    mock_get_tasks.return_value = [{"gid": "111", "name": "Fix login bug", "notes": "desc"}]
    mock_select.return_value = {"gid": "111", "name": "Fix login bug", "notes": "desc"}
    mock_clone.return_value = "/tmp/sweat_abc"
    mock_run_agent.return_value = MagicMock(success=True, summary="Fixed auth module")
    mock_create_pr.return_value = "https://github.com/augusttollerup/repo/pull/1"

    await run(dry_run=False)

    mock_assign.assert_called_once()
    mock_run_agent.assert_called_once()
    mock_create_pr.assert_called_once()
    # Comment posted twice: proposal before, PR link after
    assert mock_add_comment.call_count == 2


@pytest.mark.asyncio
@patch("main.get_unassigned_tasks")
async def test_run_exits_cleanly_when_no_task(mock_get_tasks):
    mock_get_tasks.return_value = []
    # Should not raise
    await run(dry_run=False)


@pytest.mark.asyncio
@patch("main.select_task")
@patch("main.get_unassigned_tasks")
async def test_dry_run_does_not_assign_or_clone(mock_get_tasks, mock_select):
    mock_get_tasks.return_value = [{"gid": "111", "name": "Fix login bug", "notes": "desc"}]
    mock_select.return_value = {"gid": "111", "name": "Fix login bug", "notes": "desc"}

    with patch("main.assign_task") as mock_assign, patch("main.clone_repo") as mock_clone:
        await run(dry_run=True)
        mock_assign.assert_not_called()
        mock_clone.assert_not_called()
```

**Step 2: Run to verify tests fail**

```bash
pytest tests/test_main.py -v
```
Expected: ImportError

**Step 3: Write `main.py`**

```python
import asyncio
import re
import shutil
import sys
import config
from asana_client import get_unassigned_tasks, assign_task, add_comment
from github_client import clone_repo, create_branch, commit_and_push, create_pr
from task_selector import select_task
from agent import run_agent
from prompts.task_prompt import build_agent_prompt


def _branch_name(task: dict, prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", task["name"].lower()).strip("-")[:40]
    return f"{prefix}asana-{task['gid']}-{slug}"


async def run(dry_run: bool = False) -> None:
    all_tasks = []
    for project in config.PROJECTS:
        all_tasks.extend(get_unassigned_tasks(project["asana_project_id"]))

    task = select_task(all_tasks)
    if task is None:
        print("No feasible task found. Exiting.")
        return

    print(f"Selected task: [{task['gid']}] {task['name']}")

    if dry_run:
        print("[dry-run] Would assign, clone, implement, and open PR. Exiting.")
        return

    project_cfg = next(
        p for p in config.PROJECTS
        if get_unassigned_tasks(p["asana_project_id"])  # any project that had tasks
        or True  # fallback: use first project
    )
    repo = project_cfg["github_repo"]
    branch = _branch_name(task, project_cfg["branch_prefix"])

    assign_task(task["gid"], config.ASANA_ASSIGNEE_GID)
    add_comment(task["gid"], f"I'm picking this up. Proposed approach: I'll analyse the codebase and implement a fix on branch `{branch}`. Will post the PR link here once done.")

    repo_path = clone_repo(repo)
    try:
        create_branch(repo_path, branch)
        prompt = build_agent_prompt(task, repo)
        result = await run_agent(repo_path, prompt)

        if not result.success:
            assign_task(task["gid"], "null")  # unassign
            add_comment(task["gid"], f"I ran into an error and could not complete this task:\n\n{result.error}")
            return

        commit_and_push(repo_path, branch, f"fix: {task['name'][:72]}")
        pr_url = create_pr(
            repo=repo,
            branch=branch,
            title=task["name"][:72],
            body=f"## Summary\n\n{result.summary}\n\n**Asana task:** https://app.asana.com/0/0/{task['gid']}\n\n---\n_AI-generated by sweat agent_",
        )
        add_comment(task["gid"], f"PR opened: {pr_url}")
        print(f"Done. PR: {pr_url}")
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run(dry_run=dry_run))
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main.py -v
```
Expected: 3 passed

**Step 5: Run full test suite**

```bash
pytest -v
```
Expected: all tests pass

**Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: main orchestrator with dry-run mode"
```

---

## Task 8: Manual E2E Documentation

**Files:**
- Create: `TESTING.md`

**Step 1: Write `TESTING.md`**

```markdown
# End-to-End Testing

## Prerequisites

1. Copy `.env.example` to `.env` and fill in all values
2. Set up `config.py` with a real Asana project GID and GitHub repo
3. Create a dummy Asana task in the project: "Add a TODO comment in README"
4. Ensure the GitHub repo has a `main` branch and you have push access

## Running the dry-run

```bash
python main.py --dry-run
```

Expected output:
```
Selected task: [<gid>] Add a TODO comment in README
[dry-run] Would assign, clone, implement, and open PR. Exiting.
```

## Running the full E2E

```bash
python main.py
```

Verify:
- [ ] Task in Asana is assigned to you
- [ ] A comment appears on the Asana task with the proposed approach
- [ ] A branch `agent/asana-<gid>-...` appears on GitHub
- [ ] A PR is opened with the Asana task URL in the body
- [ ] A second Asana comment appears with the PR link

## Scheduling with cron

Add to crontab (`crontab -e`):

```
0 * * * * cd /path/to/sweat && /path/to/python main.py >> /tmp/sweat.log 2>&1
```

This runs every hour. Check `/tmp/sweat.log` for output.
```

**Step 2: Commit**

```bash
git add TESTING.md
git commit -m "docs: E2E testing guide"
```

---

## Done

Run the full test suite one last time:

```bash
pytest -v
```

All tests should pass. The project is ready for manual E2E testing per `TESTING.md`.
