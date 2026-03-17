# CLI Wizard Design

**Date:** 2026-03-17
**Scope:** `cli.py` — replace `argparse` with Typer, add Rich styling to `sweat init` as a step-by-step setup wizard

---

## Context

`sweat` is an autonomous software engineering agent. Its CLI has six commands (`start`, `review`, `code-review`, `log`, `init`, `up`). Currently the CLI uses `argparse` for command dispatch and plain `print()` / `input()` / `getpass` for all output and prompts. This design covers migrating to Typer + Rich, starting with a polished `sweat init` wizard.

---

## Architecture

### Framework swap

- Replace `argparse` with **Typer** (`typer>=0.12`). Each command becomes a `@app.command()` decorated function.
- Add **Rich** (`rich>=13.0`). A module-level `console = Console()` replaces all `print()` calls.
- The agent runtime logging (`sweat start`) is **untouched** — it uses Python's `logging` module and is daemon output, not wizard UX.
- `sweat log` output stays plain text for now — it is a separate concern.

### Minimal styling for non-init commands

`sweat review`, `sweat code-review`, and `sweat up` get their `print()` calls converted to `console.print()` with minimal markup: error messages in red, success messages in green.

---

## Init Wizard Flow

`sweat init` becomes a four-step wizard. Each step is announced by a Rich `Panel` header. Credential validation runs under a `console.status()` spinner. On failure, a red `✗` message is printed and the command exits with code 1 via `raise typer.Exit(1)`.

### Step 1 / 4 — Asana

```
╭─────────────────────────────────────╮
│  Step 1 / 4 — Asana                 │
╰─────────────────────────────────────╯
Asana personal access token: ****
  ✓ Authenticated as August Tollerup
```

- Token collected with `typer.prompt(hide_input=True)`
- `AsanaClient.get_current_user()` called under a spinner
- On success: green `✓ Authenticated as {name}`
- On failure: red `✗ Invalid token — check it and try again.` + exit 1

### Step 2 / 4 — GitHub

```
╭─────────────────────────────────────╮
│  Step 2 / 4 — GitHub                │
╰─────────────────────────────────────╯
Auth method [pat/app]: pat
GitHub personal access token: ****
  ✓ Authenticated as augusttollerup
```

- Auth method via `typer.prompt()` with `pat`/`app` validation loop
- PAT: token collected with `typer.prompt(hide_input=True)`, validated via `GitHubClient.get_bot_login()`
- App: App ID via `typer.prompt()`, PEM key via multiline `input()` loop (terminated by blank line after END marker), validated via `GitHubClient.get_bot_login()`
- On success: green `✓ Authenticated as {login}`
- On failure: red `✗` message + exit 1

### Step 3 / 4 — Asana Project

```
╭─────────────────────────────────────╮
│  Step 3 / 4 — Asana Project         │
╰─────────────────────────────────────╯
  #   Workspace
 ─────────────
  1   My Workspace

Select workspace [1]: 1

  #   Project
 ──────────────
  1   Backend Tasks
  2   Frontend Tasks

Select project [1]: 2
```

- Workspaces and projects fetched under a spinner
- Each selection rendered as a two-column Rich `Table` (index + name)
- Selection via `typer.prompt()` with integer validation, defaulting to `1`
- If only one item exists, it is auto-selected and printed without a prompt

### Step 4 / 4 — GitHub Repository

```
╭─────────────────────────────────────╮
│  Step 4 / 4 — GitHub Repository     │
╰─────────────────────────────────────╯
GitHub repo (owner/name): augusttollerup/myrepo
```

- Collected via `typer.prompt()`

### Completion summary

```
╭─────────────────────────────────────╮
│  Setup complete                      │
╰─────────────────────────────────────╯
  ✓ Wrote .env
  ✓ Wrote sweat.config.json
  ✓ Wrote docker-compose.yml
```

- Each file write prints a green `✓` on success, or a yellow `→ Skipped {path} (already exists)` if the file exists

---

## Dependencies

Add to `pyproject.toml` under `[project] dependencies`:

```
typer>=0.12
rich>=13.0
```

No other dependencies change.

---

## Testing

No new tests are required. The existing test suite does not cover the CLI layer — tests target agents, clients, and task logic. The `sweat init` refactor preserves the identical logical flow (same credential validation, same file writes); no test coverage regresses. All agent/client code is untouched.

---

## Out of Scope

- `sweat log` table styling (separate task)
- `sweat start` live agent status display (separate task)
- Arrow-key select menus (Questionary) for workspace/project selection
