# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                              # Install dependencies (never use pip)
uv run pytest -v                     # Run all tests
uv run pytest tests/test_foo.py -v   # Run a single test file
uv run pytest -k "test_name" -v      # Run a single test by name
uv run sweat init                    # Interactive setup: create .env + sweat.config.json + docker-compose.yml
uv run sweat up                      # Build Docker image and start via Compose
uv run sweat up -d                   # Same, detached (background)
uv run sweat start                   # Start agents directly (used inside container)
uv run sweat review                  # Run reviewer agents once
uv run sweat log --last 20           # View recent audit log entries
uv run python main.py --dry-run      # Run first implementer once in dry-run mode
```

No linter or formatter is configured.

## Architecture

**sweat** is an autonomous software engineering agent. It picks unassigned Asana tasks, implements them via Claude Code SDK, and opens GitHub PRs. A second agent type reviews PRs.

### Agent system (`agents/`)

All agents inherit `BaseAgent` (in `agents/base.py`) which defines `run_once()` and receives injectable `GitHubClient` + `AsanaClient` instances. Agent types are registered in `agents/registry.py` and instantiated from `config.AGENTS` by the CLI scheduler.

- **ImplementerAgent** — fetches tasks → filters (`task_filter.py`) → selects via Claude (`task_selector.py`) → clones repo → runs Claude Code SDK (`agent.py`) → commits, pushes, opens PR
- **ReviewerAgent** — polls open PRs → skips self-authored and already-reviewed → runs Claude Code SDK to produce a review → posts via GitHub API

### Client layer (`clients/`)

`GitHubClient` and `AsanaClient` are classes that take auth tokens at init. They wrap PyGithub and the Asana v5 SDK respectively. Agents receive clients via constructor injection — this is what enables multiple agents with different credentials.

### Config (`config.py`)

`AGENTS` is a list of agent instance definitions. Each entry specifies `type` (implementer/reviewer), `interval`, `projects` (Asana project → GitHub repo mappings), and agent-specific settings like `asana_assignee_gid`. To add a new agent targeting a different repo, add another entry to this list.

### Claude Code SDK usage (`agent.py`, `task_selector.py`)

Both use `claude_agent_sdk.query()` to run Claude headlessly. `agent.py` runs implementation/review prompts with `permission_mode="acceptEdits"`. `task_selector.py` uses it for structured task selection (JSON output). Both handle exit code 1 as an auth error.

### Test conventions

- pytest with `asyncio_mode = "auto"` — async tests need no decorator
- `conftest.py` sets dummy env vars so `config.py` imports don't fail during collection
- External calls (Asana, GitHub, Claude SDK) are always mocked
- Client tests patch the underlying SDK classes (`clients.github.Github`, `clients.asana._Client`)
- Agent tests inject `MagicMock(spec=GitHubClient)` / `MagicMock(spec=AsanaClient)` directly — no module-level patching needed for clients

## Environment variables

`ASANA_TOKEN`, `GITHUB_TOKEN`, `ASANA_ASSIGNEE_GID` (required). `AUDIT_LOG_PATH` (optional, defaults to `audit.jsonl`). See `.env.example`.
