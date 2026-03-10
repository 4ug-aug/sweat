# Digital Twin Agent — Design Doc
**Date:** 2026-03-10
**Project:** sweat (Software Engineer August Tollerup)

## Goal

An agentic platform that acts as a digital twin. On a schedule, it finds a feasible Asana task, takes ownership, proposes a solution, implements it on a branch via Claude Code SDK, and opens a pull request.

---

## Architecture

```
sweat/
├── main.py                  # entrypoint, cron target
├── config.py                # env vars, project/repo mappings
├── asana_client.py          # Asana API: list tasks, assign, comment
├── github_client.py         # GitHub API: create branch, push PR
├── agent.py                 # Claude Code SDK interface: clone repo, run agent
├── task_selector.py         # Claude picks best feasible task from list
├── prompts/
│   └── task_prompt.py       # builds the prompt for Claude Code
├── .env                     # ASANA_TOKEN, ANTHROPIC_KEY, GITHUB_TOKEN
└── requirements.txt
```

**Stack:** Python, Claude Code SDK (headless), Asana REST API, PyGithub

---

## Flow Per Cron Run

1. Fetch unassigned tasks from all configured Asana projects
2. Feed task list to Claude → returns the one task it's most confident it can implement, or `null` (exit cleanly)
3. Assign task to configured Asana user, post proposal comment
4. Clone target GitHub repo to `tempfile.mkdtemp()`
5. Run Claude Code SDK headlessly with prompt containing task description + repo context
6. Push branch `agent/asana-<task-id>-<slug>`, open PR
7. Post PR link back to Asana, cleanup temp dir

---

## Configuration

```python
# config.py
PROJECTS = [
    {
        "asana_project_id": "...",
        "github_repo": "augusttollerup/some-repo",
        "branch_prefix": "agent/",
    }
]
```

Multiple project→repo mappings supported. Each run picks one task across all configured projects.

---

## Key Decisions

| Decision | Choice |
|---|---|
| Task selection | Heuristic scoring: Claude reads task name + description + subtasks, returns best candidate or null |
| Branch naming | `agent/asana-<task-id>-<slug>` |
| PR body | Asana task URL + Claude's solution summary + AI-generated disclaimer |
| Asana comment (before) | Proposal + solution sketch |
| Asana comment (after) | Updated with PR link |
| Failure handling | Unassign task, post failure comment to Asana |
| Scheduling | External cron (e.g. crontab or launchd) calls `python main.py` |
| Claude invocation | Behind a thin interface `run_agent(repo_path, prompt) -> AgentResult` |

---

## Verification

- **Unit tests** mock Anthropic API, Asana client, GitHub client, and `run_agent` interface — no real Claude invoked
- **Dry-run mode:** `python main.py --dry-run` — runs up to agent call, prints what would happen, no side effects
- **Manual E2E:** documented in `TESTING.md`, run against a real dummy Asana task + throwaway repo

---

## Out of Scope (V1)

- Parallel task handling (one task per run)
- Self-healing / retry logic beyond simple failure comment
- Task prioritization beyond feasibility scoring
- Cloud deployment (runs locally or on any machine with Python + Claude Code installed)
