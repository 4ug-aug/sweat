# sweat — Software Engineer August Tollerup

**sweat** is an agentic platform that acts as a digital twin software engineer. It runs on a schedule, finds a software task in Asana that it can realistically implement, takes ownership of it, proposes a solution, writes the code using Claude Code, and opens a GitHub pull request — all autonomously.

---

## How It Works

```
Cron
 └── main.py
      ├── 1. Fetch unassigned tasks from Asana projects
      ├── 2. Ask Claude to pick the most feasible task
      ├── 3. Assign task + post proposal comment in Asana
      ├── 4. Clone the target GitHub repo to a temp dir
      ├── 5. Run Claude Code SDK (headless) to implement the fix
      ├── 6. Commit + push branch, open GitHub PR
      └── 7. Post PR link back to Asana, clean up temp dir
```

### Step-by-step

**1. Fetch tasks**

`asana_client.get_unassigned_tasks(project_id)` calls the Asana API and returns all tasks in a configured project that have no assignee. Multiple projects can be configured.

**2. Task selection**

`task_selector.select_task(tasks)` sends the full task list to Claude via `claude-agent-sdk`. Claude evaluates each task for feasibility — it prefers tasks with clear bug descriptions, specific acceptance criteria, or small scope — and returns the GID of the one task it's most confident it can implement, or `null` if nothing is suitable. If `null`, the run exits cleanly.

**3. Take ownership in Asana**

`asana_client.assign_task(task_id, user_gid)` assigns the task to the configured user. `asana_client.add_comment(task_id, text)` posts a comment naming the branch and promising a PR link.

**4. Clone the repo**

`github_client.clone_repo(repo)` clones the target GitHub repo into a fresh `tempfile.mkdtemp()` directory using a token-authenticated HTTPS URL. A new branch (`agent/asana-<gid>-<slug>`) is created via `github_client.create_branch`.

**5. Run Claude Code**

`agent.run_agent(repo_path, prompt)` invokes the `claude-agent-sdk` headlessly with `permission_mode="acceptEdits"` and `cwd` set to the cloned repo. Claude explores the codebase, implements the fix, and writes or updates tests. It does **not** commit — the orchestrator handles git.

The prompt is built by `prompts.task_prompt.build_agent_prompt(task, repo)`, which includes the task name, description, Asana GID, and instructions.

**6. Commit, push, open PR**

`github_client.commit_and_push` stages all changes and pushes the branch. `github_client.create_pr` opens a pull request on GitHub with a body that includes Claude's summary and a link back to the Asana task.

**7. Report back and clean up**

A second Asana comment is posted with the PR URL. The temp directory is deleted in a `finally` block regardless of success or failure.

**On failure:** If Claude Code returns an error, the task is unassigned and an error comment is posted to Asana so it's visible and can be retried.

---

## Authentication

sweat authenticates via **Claude Code** — no Anthropic API key is needed. Both the task selector and the coding agent use `claude-agent-sdk`, which routes through your local Claude Code installation.

---

## Project Structure

```
sweat/
├── cli.py                   # Service entrypoint — runs both loops concurrently
├── main.py                  # Implementer — picks a task, writes code, opens PR
├── pr_poller.py             # PR reviewer poller — finds unreviewed PRs
├── pr_reviewer.py           # Orchestrates a single PR review end-to-end
├── config.py                # Loads env vars and project/repo mappings
├── asana_client.py          # Asana API: list tasks, assign, comment
├── github_client.py         # GitHub: clone, branch, push, open/review PRs
├── task_selector.py         # Claude picks the most feasible task
├── agent.py                 # claude-agent-sdk wrapper
├── prompts/
│   ├── task_prompt.py       # Builds the implementation prompt for Claude Code
│   └── review_prompt.py     # Builds the PR review prompt for Claude Code
├── tests/                   # Unit tests (all external calls mocked)
├── pyproject.toml           # uv project config and dependencies
├── .env.example             # Template for required env vars
└── TESTING.md               # Manual E2E testing guide
```

---

## Configuration

Copy `.env.example` to `.env` and fill in:

```bash
ASANA_TOKEN=your_asana_personal_access_token
GITHUB_TOKEN=your_github_personal_access_token
ASANA_ASSIGNEE_GID=your_asana_user_gid
```

Edit `config.py` to add your Asana project → GitHub repo mappings:

```python
PROJECTS = [
    {
        "asana_project_id": "1234567890",       # Asana project GID
        "github_repo": "augusttollerup/myrepo", # GitHub repo
        "branch_prefix": "agent/",              # Branch prefix
    }
]
```

Multiple projects are supported — the agent picks one task across all of them per run.

---

## Running

**Install dependencies:**

```bash
uv sync
```

**Start the service:**

```bash
uv run python cli.py start
```

This starts two loops concurrently:
- **Implementer** — picks and implements an Asana task, opens a PR (default: every hour)
- **PR reviewer** — reviews open PRs that haven't been reviewed by the bot yet (default: every 60s)

Ctrl-C or `SIGTERM` shuts both down cleanly.

**Custom intervals:**

```bash
uv run python cli.py start --implement-interval 1800 --review-interval 30
```

**Dry run** (no side effects — prints what the implementer would do):

```bash
uv run python main.py --dry-run
```

---

## Testing

```bash
uv run pytest -v
```

All 22 tests run in under a second. No real API calls are made — Asana, GitHub, and the Claude SDK are all mocked at the interface boundary.

See `TESTING.md` for the manual end-to-end test procedure.

---

## Dependencies

| Package | Purpose |
|---|---|
| `claude-agent-sdk` | Task selection + headless Claude Code execution |
| `asana` | Asana REST API client |
| `PyGithub` | GitHub API (PR creation) |
| `GitPython` | Git operations (clone, branch, push) |
| `python-dotenv` | `.env` file loading |
