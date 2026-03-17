# CLI Wizard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `argparse` with Typer and add Rich styling to `cli.py`, including a polished four-step `sweat init` setup wizard.

**Architecture:** All changes are confined to `cli.py` and `pyproject.toml`. The Typer app replaces the `argparse`+`main()` dispatch pattern; `asyncio.run()` calls and `_configure_logging()` move into individual command functions; all `print()` calls become `console.print()` with Rich markup; `_cmd_init()` is rewritten as a wizard with panels, spinners, and validation loops.

**Tech Stack:** Python 3.11+, `typer>=0.12`, `rich>=13.0`, existing `clients.asana.AsanaClient`, `clients.github.GitHubClient`

---

## Chunk 1: Dependencies, Typer Skeleton, Non-Init Migrations

### Task 1: Add typer and rich to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the two new entries to the dependencies list**

In `pyproject.toml`, the `dependencies` list currently ends with `"opentelemetry-exporter-otlp-proto-grpc>=1.20.0"`. Add two lines after it:

```toml
dependencies = [
    "claude-agent-sdk>=0.0.14",
    "asana>=5.0.0",
    "PyGithub>=2.1.1",
    "GitPython>=3.1.41",
    "python-dotenv>=1.0.0",
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-exporter-otlp-proto-grpc>=1.20.0",
    "typer>=0.12",
    "rich>=13.0",
]
```

- [ ] **Step 2: Sync the environment**

```bash
uv sync
```

Expected: resolves successfully, no errors.

- [ ] **Step 3: Verify imports work**

```bash
uv run python -c "import typer, rich; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add typer and rich dependencies"
```

---

### Task 2: Replace argparse with a Typer skeleton

**Files:**
- Modify: `cli.py`

This task replaces the `argparse` setup and `main()` with Typer, wires all six commands to the same internal `_cmd_*` functions they already call, and moves `asyncio.run()` + `_configure_logging()` into the command functions. **Do not change any `_cmd_*` implementations yet.**

- [ ] **Step 1: Update imports at the top of cli.py**

Replace:
```python
import argparse
```

With:
```python
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
```

Keep `import getpass` for now — it is still used by the old `_cmd_init` (removed in Task 4).
Keep `import sys` for now — it is still used by the old `_cmd_init` (removed in Task 4). Note: Task 3 removes `sys.exit()` from `_cmd_up`, but `sys` remains referenced by `_cmd_init` until Task 4.

Add a module-level console instance after the existing imports block (after the `from clients.github import GitHubClient` line):

```python
console = Console()
app = typer.Typer(help="sweat — agentic software engineer service")
```

- [ ] **Step 2: Replace the main() function and add Typer command functions**

Delete the entire `main()` function at the bottom of `cli.py`. Replace it with the following six command functions and a new `main()`:

```python
@app.command()
def start() -> None:
    """Start all configured agents."""
    _configure_logging()
    telemetry.init()
    asyncio.run(_start())


@app.command()
def review() -> None:
    """Run reviewer agents once and exit."""
    _configure_logging()
    asyncio.run(_run_once("reviewer"))


@app.command(name="code-review")  # explicit to document the CLI name; Typer would auto-convert underscores to hyphens anyway
def code_review() -> None:
    """Run code review agents once and exit."""
    _configure_logging()
    asyncio.run(_run_once("code_reviewer"))


@app.command()
def log(
    last: int = typer.Option(20, "--last", help="Number of recent entries to show"),
) -> None:
    """View recent audit log entries."""
    _cmd_log(last)


@app.command()
def init() -> None:
    """Interactive setup: create .env, sweat.config.json, and docker-compose.yml."""
    _cmd_init()


@app.command()
def up(
    detach: bool = typer.Option(False, "--detach", "-d", help="Run containers in background"),
) -> None:
    """Build and start sweat via Docker Compose."""
    _cmd_up(detach)


def main() -> None:
    app()
```

- [ ] **Step 3: Verify CLI loads and help works**

```bash
uv run python cli.py --help
```

Expected: Typer-formatted help listing all six commands (`start`, `review`, `code-review`, `log`, `init`, `up`). When no subcommand is given, Typer prints help and exits 0 — this replaces the old `parser.print_help()` fallback, same behavior.

```bash
uv run python cli.py log --help
```

Expected: shows `--last INTEGER` option with default `20`.

```bash
uv run sweat-agent --help
```

Expected: same Typer-formatted help via the installed entry point (`sweat-agent` is the registered script name in `pyproject.toml`).

- [ ] **Step 4: Run existing tests**

```bash
uv run pytest -v
```

Expected: 143 tests pass (CLI layer is not tested; agent/client logic is unchanged).

- [ ] **Step 5: Commit**

```bash
git add cli.py
git commit -m "feat: replace argparse with Typer skeleton"
```

---

### Task 3: Migrate non-init commands to Rich output

**Files:**
- Modify: `cli.py`

- [ ] **Step 1: Update `_cmd_log` to use `console.print()`**

Replace the existing `_cmd_log` function with:

```python
def _cmd_log(last: int) -> None:
    path = config.AUDIT_LOG_PATH
    if not os.path.exists(path):
        console.print(f"No audit log found at {path}")
        return
    with open(path) as f:
        lines = f.readlines()
    for raw_line in lines[-last:]:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            record = json.loads(raw_line)
            console.print(_format_log_entry(record))
        except json.JSONDecodeError:
            console.print(raw_line)
```

Note: the loop variable is renamed `raw_line` (was `line`) for clarity.

No markup or colour — the log output stays as plain text strings.

- [ ] **Step 2: Update `_cmd_up` to use `console.print()` and `typer.Exit()`**

Replace the existing `_cmd_up` function with:

```python
def _cmd_up(detach: bool) -> None:
    if not (Path.cwd() / "docker-compose.yml").exists():
        console.print("[red]No docker-compose.yml found. Run 'sweat init' first.[/red]")
        raise typer.Exit(1)
    cmd = ["docker", "compose", "up", "--build"]
    if detach:
        cmd.append("-d")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Docker Compose failed (exit code {e.returncode})[/red]")
        raise typer.Exit(code=e.returncode)
```

- [ ] **Step 3: Run existing tests**

```bash
uv run pytest -v
```

Expected: 143 tests pass.

- [ ] **Step 4: Commit**

```bash
git add cli.py
git commit -m "feat: migrate non-init commands to Rich console output"
```

---

## Chunk 2: Init Wizard

> **Prerequisite:** Chunk 1 must be complete. By this point `typer` and `rich` are installed, `cli.py` already imports them, `console = Console()` and `app = typer.Typer(...)` exist at module level, and `argparse` has been replaced with Typer command functions.

### Task 4: Rewrite `_cmd_init` as a four-step Rich wizard

**Files:**
- Modify: `cli.py`

This is the main deliverable. Replace `_cmd_init()` and remove `_pick()` and the now-unused `import getpass` and `import sys`.

- [ ] **Step 1: Remove the `_pick()` function**

Delete the entire `_pick()` function from `cli.py` (currently lines 211–224). It is replaced by inline `while True` selection loops in the new `_cmd_init`.

- [ ] **Step 2: Replace `_cmd_init()` with the wizard**

Replace the entire `_cmd_init()` function with:

```python
def _cmd_init() -> None:
    """Interactive setup: validate credentials, discover config, write files."""
    console.print(Panel("[bold]sweat init — interactive setup[/bold]"))

    # ── Step 1 / 4 — Asana ──────────────────────────────────────────────
    console.print(Panel("[bold]Step 1 / 4 — Asana[/bold]"))
    asana_token = typer.prompt("Asana personal access token", hide_input=True)
    asana_client = AsanaClient(asana_token)
    with console.status("Validating...") as status:
        try:
            me = asana_client.get_current_user()
            asana_assignee_gid = me["gid"]
        except Exception:
            status.stop()
            console.print("[red]  ✗ Invalid token — check it and try again.[/red]")
            raise typer.Exit(1)
    status.stop()
    console.print(f"[green]  ✓ Authenticated as {me['name']}[/green]")

    # ── Step 2 / 4 — GitHub ─────────────────────────────────────────────
    console.print(Panel("[bold]Step 2 / 4 — GitHub[/bold]"))
    while True:
        auth_choice = typer.prompt("Auth method [pat/app]")
        if auth_choice in ("pat", "app"):
            break
        console.print("[red]  ✗ Please enter 'pat' or 'app'.[/red]")

    if auth_choice == "pat":
        github_token = typer.prompt("GitHub personal access token", hide_input=True)
        with console.status("Validating...") as status:
            try:
                gh_client = GitHubClient(token=github_token)
                gh_login = gh_client.get_bot_login()
            except Exception:
                status.stop()
                console.print("[red]  ✗ Invalid token — check it and try again.[/red]")
                raise typer.Exit(1)
        status.stop()
        console.print(f"[green]  ✓ Authenticated as {gh_login}[/green]")
        github_env_lines = f"GITHUB_TOKEN={github_token}\n"
    else:
        github_app_id = typer.prompt("GitHub App ID")
        console.print("Paste private key PEM (paste all lines, end with a blank line after the END marker):")
        lines: list[str] = []
        while True:
            line = input()
            if line == "" and lines and "END" in lines[-1]:
                break
            lines.append(line)
        github_private_key = "\n".join(lines)
        with console.status("Validating...") as status:
            try:
                gh_client = GitHubClient(app_id=github_app_id, private_key=github_private_key)
                gh_login = gh_client.get_bot_login()
            except Exception:
                status.stop()
                console.print("[red]  ✗ Invalid App ID or private key — check them and try again.[/red]")
                raise typer.Exit(1)
        status.stop()
        console.print(f"[green]  ✓ Authenticated as app '{gh_login}'[/green]")
        escaped_key = github_private_key.replace("\n", "\\n")
        github_env_lines = f"GITHUB_APP_ID={github_app_id}\nGITHUB_APP_PRIVATE_KEY={escaped_key}\n"

    # ── Step 3 / 4 — Asana Project ───────────────────────────────────────
    console.print(Panel("[bold]Step 3 / 4 — Asana Project[/bold]"))
    with console.status("Fetching workspaces...") as status:
        try:
            workspaces = asana_client.get_workspaces()
        except Exception:
            status.stop()
            console.print("[red]  ✗ Failed to fetch Asana workspaces.[/red]")
            raise typer.Exit(1)
    status.stop()

    if not workspaces:
        console.print("[red]  ✗ No Asana workspaces found for this token.[/red]")
        raise typer.Exit(1)

    if len(workspaces) == 1:
        workspace = workspaces[0]
        console.print(f"  Using workspace: {workspace['name']}")
    else:
        table = Table("#", "Workspace", box=None, show_header=True, header_style="bold")
        for i, ws in enumerate(workspaces, 1):
            table.add_row(str(i), ws["name"])
        console.print(table)
        while True:
            raw = typer.prompt("Select workspace", default="1")
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(workspaces):
                    workspace = workspaces[idx]
                    break
            except ValueError:
                pass
            console.print(f"[red]  ✗ Please enter a number between 1 and {len(workspaces)}.[/red]")

    with console.status("Fetching projects...") as status:
        try:
            projects = asana_client.get_projects(workspace["gid"])
        except Exception:
            status.stop()
            console.print(f"[red]  ✗ Failed to fetch projects for workspace '{workspace['name']}'.[/red]")
            raise typer.Exit(1)
    status.stop()

    if not projects:
        console.print(f"[red]  ✗ No projects found in workspace '{workspace['name']}'.[/red]")
        raise typer.Exit(1)

    if len(projects) == 1:
        project = projects[0]
        console.print(f"  Using project: {project['name']}")
    else:
        table = Table("#", "Project", box=None, show_header=True, header_style="bold")
        for i, p in enumerate(projects, 1):
            table.add_row(str(i), p["name"])
        console.print(table)
        while True:
            raw = typer.prompt("Select project", default="1")
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(projects):
                    project = projects[idx]
                    break
            except ValueError:
                pass
            console.print(f"[red]  ✗ Please enter a number between 1 and {len(projects)}.[/red]")

    asana_project_id = project["gid"]

    # ── Step 4 / 4 — GitHub Repository ──────────────────────────────────
    console.print(Panel("[bold]Step 4 / 4 — GitHub Repository[/bold]"))
    while True:
        github_repo = typer.prompt("GitHub repo (owner/name)")
        parts = github_repo.split("/")
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            break
        console.print("[red]  ✗ Repo must be in owner/name format (e.g. myorg/myrepo).[/red]")

    cwd = Path.cwd()

    # Write .env
    env_path = cwd / ".env"
    if not env_path.exists():
        env_path.write_text(
            f"ASANA_TOKEN={asana_token}\n"
            f"{github_env_lines}"
            f"ASANA_ASSIGNEE_GID={asana_assignee_gid}\n"
        )
        env_msg = f"[green]  ✓ Wrote {env_path}[/green]"
    else:
        env_msg = f"[yellow]  → Skipped {env_path} (already exists)[/yellow]"

    # Write sweat.config.json
    starter_config = {
        "agents": [
            {
                "id": "implementer",
                "type": "implementer",
                "interval": 3600,
                "asana_assignee_gid": asana_assignee_gid,
                "projects": [
                    {
                        "asana_project_id": asana_project_id,
                        "github_repo": github_repo,
                        "branch_prefix": "agent/",
                        "field_names": {},
                        "field_filters": {},
                        "priority_order": ["High", "Medium", "Low"],
                        "max_tasks_for_selector": 15,
                    }
                ],
            },
            {
                "id": "reviewer",
                "type": "reviewer",
                "interval": 60,
                "projects": [
                    {
                        "github_repo": github_repo,
                        "branch_prefix": "agent/",
                    }
                ],
            },
        ]
    }
    config_path = cwd / "sweat.config.json"
    if not config_path.exists():
        config_path.write_text(json.dumps(starter_config, indent=2) + "\n")
        config_msg = f"[green]  ✓ Wrote {config_path}[/green]"
    else:
        config_msg = f"[yellow]  → Skipped {config_path} (already exists)[/yellow]"

    # Write docker-compose.yml
    compose_path = cwd / "docker-compose.yml"
    if not compose_path.exists():
        compose_path.write_text(_COMPOSE_TEMPLATE)
        compose_msg = f"[green]  ✓ Wrote {compose_path}[/green]"
    else:
        compose_msg = f"[yellow]  → Skipped {compose_path} (already exists)[/yellow]"

    console.print(Panel("[bold]Setup complete[/bold]"))
    console.print(env_msg)
    console.print(config_msg)
    console.print(compose_msg)
    console.print("\nNext steps:")
    console.print("  1. Review and customize sweat.config.json (field_names, field_filters, etc.)")
    console.print("  2. Run: sweat up")
```

- [ ] **Step 3: Remove now-unused imports**

Remove these two lines from the imports at the top of `cli.py`:
```python
import getpass
import sys
```

Both are no longer used: `getpass` is replaced by `typer.prompt(hide_input=True)`, and `sys` was only used for `sys.exit()` which is now `typer.Exit()`.

- [ ] **Step 4: Run existing tests**

```bash
uv run pytest -v
```

Expected: 143 tests pass.

- [ ] **Step 5: Verify init help and basic CLI**

```bash
uv run python cli.py init --help
```

Expected: shows the `init` command description.

```bash
uv run python cli.py --help
```

Expected: clean Typer-formatted help with all six commands listed.

- [ ] **Step 6: Commit**

```bash
git add cli.py
git commit -m "feat: rewrite sweat init as four-step Rich wizard"
```
