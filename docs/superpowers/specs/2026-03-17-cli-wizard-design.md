# CLI Wizard Design

**Date:** 2026-03-17
**Scope:** `cli.py` — replace `argparse` with Typer, add Rich styling to `sweat init` as a step-by-step setup wizard

---

## Context

`sweat` is an autonomous software engineering agent. Its CLI has six commands (`start`, `review`, `code-review`, `log`, `init`, `up`). Currently the CLI uses `argparse` for command dispatch and plain `print()` / `input()` / `getpass` for all output and prompts. This design covers migrating to Typer + Rich, starting with a polished `sweat init` wizard.

**Entry point note:** The registered script in `pyproject.toml` is `sweat-agent`, not `sweat`. This design does not rename the entry point.

---

## Architecture

### Framework swap

- Replace `argparse` with **Typer** (`typer>=0.12`). Each command becomes a `@app.command()` decorated function.
- Add **Rich** (`rich>=13.0`). A module-level `console = Console()` replaces all `print()` calls.

### Async command wrappers

Typer command functions must be synchronous. The `asyncio.run()` wrappers that currently live in `main()` move inside their respective command functions:

- `start` command body: `_configure_logging()`, then `telemetry.init()`, then `asyncio.run(_start())`
- `review` command body: `_configure_logging()`, then `asyncio.run(_run_once("reviewer"))`
- `code-review` command body: `_configure_logging()`, then `asyncio.run(_run_once("code_reviewer"))`

`_configure_logging()` is **not** called for `init`, `log`, or `up` — those commands use only Rich console output, not the logging framework. This is an intentional narrowing from the current behavior (where `_configure_logging()` was called unconditionally in `main()`).

### Styling for non-init commands

**`sweat up`** has two `print()` calls to convert:
- Missing compose file: red error + `raise typer.Exit(1)` (replacing `sys.exit(1)`)
- Compose failure: red error + `raise typer.Exit(code=e.returncode)` (replacing `sys.exit(e.returncode)`)
- `subprocess.run(cmd, check=True)` is unchanged.

**`sweat review`** and **`sweat code-review`**: no `print()` calls in their code paths; changes are limited to adding `_configure_logging()` and moving `asyncio.run()` into the command body.

**`sweat log`**: `print()` → `console.print()` with no colour or markup. The `--last N` option becomes `last: int = typer.Option(20, "--last", help="Number of recent entries to show")`.

---

## Init Wizard Flow

`sweat init` is a plain synchronous `def` function (not `async def`). It becomes a four-step wizard; each step announced by a Rich `Panel` header.

**Validation pattern:** Prompt first (outside spinner). Then `console.status()` wraps only the API call. Explicitly call `status.stop()` before printing (defensive style to ensure the spinner is visually cleared):

```python
with console.status("Validating...") as status:
    try:
        result = some_api_call()
    except Exception:
        status.stop()
        console.print("[red]✗ Error[/red]")
        raise typer.Exit(1)
status.stop()
console.print("[green]✓ Success[/green]")
```

**Input loops:** `while True` + `typer.prompt()` + `break` on valid input.

**Local variables carried across steps:** `asana_client`, `asana_token`, `asana_assignee_gid`, `github_env_lines`, `asana_project_id`, `github_repo`. No global state.

### Step 1 / 4 — Asana

- Token: `typer.prompt(hide_input=True)` → construct `AsanaClient(token)`
- Spinner → `asana_client.get_current_user()` → `status.stop()`
- Success: store `asana_assignee_gid = me["gid"]`; green `✓ Authenticated as {me["name"]}`
- Failure: red `✗ Invalid token — check it and try again.` + `raise typer.Exit(1)`

### Step 2 / 4 — GitHub

- Auth method: `while True` loop; only `pat` or `app` accepted
- **PAT path:** `typer.prompt(hide_input=True)` → spinner → `GitHubClient(token=token).get_bot_login()` → `status.stop()`. Failure: red `✗ Invalid token — check it and try again.` + `raise typer.Exit(1)`. Set `github_env_lines = f"GITHUB_TOKEN={token}\n"`
- **App path:** App ID via `typer.prompt()`; PEM key via raw `input()` loop (intentionally retained — `typer.prompt()` cannot collect multiline input). Loop collects lines until the user enters a blank line immediately after a line that **contains** the substring `"END"` (e.g. `"-----END RSA PRIVATE KEY-----"`). Before writing to `.env`, newlines in the key are escaped: `escaped_key = private_key.replace("\n", "\\n")`. Spinner → `GitHubClient(app_id=..., private_key=...).get_bot_login()` → `status.stop()`. Failure: red `✗ Invalid App ID or private key — check them and try again.` + `raise typer.Exit(1)`. Set `github_env_lines = f"GITHUB_APP_ID={app_id}\nGITHUB_APP_PRIVATE_KEY={escaped_key}\n"`
- Success (both paths): green `✓ Authenticated as {login}`

### Step 3 / 4 — Asana Project

- Spinner → `asana_client.get_workspaces()` → `status.stop()`. Exception: red `✗ Failed to fetch Asana workspaces.` + `raise typer.Exit(1)`
- 0 workspaces: red `✗ No Asana workspaces found for this token.` + `raise typer.Exit(1)`
- 1 workspace: `console.print(f"Using workspace: {name}")`, no prompt
- Multiple: Rich `Table` + `while True` loop defaulting to `"1"`; invalid → red `✗ Please enter a number between 1 and {n}.`
- Same for projects (`asana_client.get_projects(workspace_gid)`):
  - Exception: red `✗ Failed to fetch projects for workspace '{workspace_name}'.` + `raise typer.Exit(1)`
  - 0 projects: red `✗ No projects found in workspace '{workspace_name}'.` + `raise typer.Exit(1)`
  - 1: auto-selected; multiple: table + loop
- Store selected project `gid` as `asana_project_id`

### Step 4 / 4 — GitHub Repository

- `while True` + `typer.prompt()`
- Valid: `repo.split("/")` yields exactly 2 non-empty parts. Invalid: red `✗ Repo must be in owner/name format (e.g. myorg/myrepo).`

### Completion summary

- Rich `Panel` "Setup complete"
- Green `✓ Wrote {file}` or yellow `→ Skipped {file} (already exists)` for `.env`, `sweat.config.json`, `docker-compose.yml`
- "Next steps" block printed below panel (text preserved exactly from current implementation)

---

## Dependencies

Add to `pyproject.toml` under `[project] dependencies`:

```
typer>=0.12
rich>=13.0
```

---

## Testing

No new tests required. The CLI layer is not currently tested; the logical flow is unchanged.

---

## Out of Scope

- `sweat log` table styling
- `sweat start` live display
- Arrow-key select menus
- Entry point rename
