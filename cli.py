"""
sweat CLI — start the background service.

Usage:
    sweat start
    sweat review
    sweat log [--last N]
    sweat init
"""
import asyncio
import json
import logging
import os
import signal
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config
import telemetry

from agents.registry import AGENT_TYPES
from clients.asana import AsanaClient
from clients.github import GitHubClient

console = Console()
app = typer.Typer(help="sweat — agentic software engineer service")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_agents(type_filter: str | None = None):
    """Instantiate agents from config, optionally filtering by type.

    Supports ``replicas`` (default 1) per agent config entry.  Each replica
    gets a unique id (``{base_id}-{i}``) and a staggered ``initial_delay``
    so that replicas don't all fire at the same instant.
    """
    if not config.ASANA_TOKEN or (not config.GITHUB_TOKEN and not (config.GITHUB_APP_ID and config.GITHUB_APP_PRIVATE_KEY)):
        logging.error("ASANA_TOKEN and GitHub credentials (GITHUB_TOKEN or GITHUB_APP_ID+GITHUB_APP_PRIVATE_KEY) must be set. Run 'sweat init' to configure.")
        return []

    github = GitHubClient(
        token=config.GITHUB_TOKEN,
        app_id=config.GITHUB_APP_ID,
        private_key=config.GITHUB_APP_PRIVATE_KEY,
    )
    asana = AsanaClient(config.ASANA_TOKEN)

    agents = []
    for agent_cfg in config.AGENTS:
        agent_type = agent_cfg["type"]
        if type_filter and agent_type != type_filter:
            continue
        cls = AGENT_TYPES.get(agent_type)
        if cls is None:
            logging.warning(f"Unknown agent type: {agent_type!r}, skipping")
            continue

        replicas = agent_cfg.get("replicas", 1)

        for i in range(replicas):
            agent_id = agent_cfg["id"] if replicas == 1 else f"{agent_cfg['id']}-{i}"
            agent = cls(
                agent_id=agent_id,
                config=agent_cfg,
                github=github,
                asana=asana,
            )
            interval = agent_cfg.get("interval", agent.default_interval)
            for loop_name, loop_interval in agent.get_loops().items():
                loop_initial_delay = i * (loop_interval / replicas) if replicas > 1 else 0
                agents.append((agent, loop_name, loop_interval, loop_initial_delay))
    return agents


async def _agent_loop(agent, loop_name: str, interval: int, initial_delay: float = 0) -> None:
    if initial_delay > 0:
        logging.info(f"Agent {agent.agent_id!r} waiting {initial_delay:.0f}s before first run")
        await asyncio.sleep(initial_delay)
    logging.info(f"Agent {agent.agent_id!r} [{loop_name}] loop started (every {interval}s)")
    while True:
        tracer = telemetry.tracer()
        with tracer.start_as_current_span(
            "agent.run_once",
            attributes={"agent.id": agent.agent_id, "agent.type": agent.config.get("type", ""), "agent.loop": loop_name},
        ) as span:
            try:
                logging.info(f"Agent {agent.agent_id!r} [{loop_name}]: running")
                if telemetry.agent_runs:
                    telemetry.agent_runs.add(1, {"agent.id": agent.agent_id})
                start = time.monotonic()
                await agent.run_loop(loop_name)
                if telemetry.agent_run_duration:
                    telemetry.agent_run_duration.record(time.monotonic() - start, {"agent.id": agent.agent_id})
            except Exception as exc:
                span.set_status(telemetry.trace.StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                if telemetry.agent_errors:
                    telemetry.agent_errors.add(1, {"agent.id": agent.agent_id})
                logging.error(f"Agent {agent.agent_id!r}: error — {exc}")
        await asyncio.sleep(interval)


async def _start() -> None:
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set_result, None)

    agents = _build_agents()
    if not agents:
        logging.error("No agents configured. Check config.AGENTS.")
        return

    logging.info(f"sweat service starting — {len(agents)} agent(s)")
    tasks = [asyncio.create_task(_agent_loop(agent, loop_name, interval, delay)) for agent, loop_name, interval, delay in agents]
    try:
        await stop
    finally:
        logging.info("sweat service shutting down")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _run_once(type_filter: str) -> None:
    agents = _build_agents(type_filter=type_filter)
    for agent, _loop_name, _interval, _delay in agents:
        await agent.run_once()


def _format_log_entry(record: dict) -> str:
    ts = record.get("timestamp", "")[:19].replace("T", " ")
    event = record.get("event", "")
    repo = record.get("repo", "")
    agent_id = record.get("agent_id", "")
    repo_part = f"[{repo}] " if repo else ""
    agent_part = f"({agent_id}) " if agent_id else ""

    if event == "task_selected":
        detail = f"{record.get('task_name', '')} (asana:{record.get('task_gid', '')})"
    elif event == "no_task_found":
        detail = "no feasible task"
    elif event == "implementation_succeeded":
        detail = f"PR: {record.get('pr_url', '')}"
    elif event == "implementation_failed":
        detail = f"error: {record.get('error', '')}"
    elif event == "pr_review_posted":
        detail = f"PR #{record.get('pr_number', '')}: {record.get('pr_title', '')}"
    elif event == "pr_review_failed":
        detail = f"PR #{record.get('pr_number', '')} — {record.get('error', '')}"
    elif event == "pr_skipped":
        detail = f"PR #{record.get('pr_number', '')} — {record.get('reason', '')}"
    elif event == "code_review_completed":
        detail = f"{record.get('findings_count', 0)} findings, {record.get('tasks_created', 0)} tasks created"
    elif event == "code_review_task_created":
        detail = f"{record.get('title', '')} [{record.get('priority', '')}]"
    elif event == "code_review_skipped":
        detail = f"skipped — {record.get('reason', '')}"
    elif event == "code_review_failed":
        detail = f"error: {record.get('error', '')}"
    elif event == "code_review_duplicate_skipped":
        detail = f"duplicate: {record.get('title', '')}"
    elif event == "review_feedback_addressed":
        detail = f"PR #{record.get('pr_number', '')} in {repo}"
    elif event == "ci_failure_addressed":
        detail = f"PR #{record.get('pr_number', '')} in {repo}"
    elif event == "pr_comment_addressed":
        detail = f"PR #{record.get('pr_number', '')} in {repo}"
    else:
        detail = str({k: v for k, v in record.items() if k not in ("timestamp", "event", "repo", "agent_id")})

    return f"{ts}  {agent_part}{event:<30} {repo_part}{detail}"


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
            console.print(_format_log_entry(record), markup=False)
        except json.JSONDecodeError:
            console.print(raw_line, markup=False)


def _cmd_init() -> None:
    """Interactive setup: validate credentials, discover config, write files."""
    console.print(Panel("[bold]sweat init — interactive setup[/bold]"))

    # ── Step 1 / 4 — Asana ──────────────────────────────────────────────
    console.print(Panel("[bold]Step 1 / 4 — Asana[/bold]"))
    asana_token = typer.prompt("Asana personal access token", hide_input=True).strip()
    asana_client = AsanaClient(asana_token)
    with console.status("Validating...") as status:
        try:
            me = asana_client.get_current_user()
            asana_assignee_gid = me["gid"]
        except Exception as exc:
            status.stop()
            console.print(f"[red]  ✗ Asana validation failed: {exc}[/red]")
            raise typer.Exit(1)
    status.stop()
    console.print(f"[green]  ✓ Authenticated as {me['name']}[/green]")

    # ── Step 2 / 4 — GitHub ─────────────────────────────────────────────
    console.print(Panel("[bold]Step 2 / 4 — GitHub[/bold]"))
    auth_table = Table("#", "Method", "Description", box=None, show_header=True, header_style="bold")
    auth_table.add_row("1", "PAT", "Personal Access Token — simple, tied to your user account")
    auth_table.add_row("2", "App", "GitHub App — recommended for bots, fine-grained permissions")
    console.print(auth_table)
    while True:
        raw = typer.prompt("Select auth method", default="1")
        if raw == "1":
            auth_choice = "pat"
            break
        if raw == "2":
            auth_choice = "app"
            break
        console.print("[red]  ✗ Please enter 1 or 2.[/red]")

    if auth_choice == "app":
        console.print(Panel(
            "[bold]GitHub App setup guide[/bold]\n\n"
            "1. Go to [bold]github.com/settings/apps/new[/bold] (or your org's Settings → Developer settings → GitHub Apps)\n"
            "2. Give the app a name and set Homepage URL to anything\n"
            "3. Under [bold]Permissions[/bold], grant:\n"
            "     • Contents: Read & Write\n"
            "     • Pull requests: Read & Write\n"
            "     • Issues: Read & Write (optional, for task comments)\n"
            "4. Click [bold]Create GitHub App[/bold] — note the [bold]App ID[/bold] at the top of the settings page\n"
            "5. Scroll down and click [bold]Generate a private key[/bold] — this downloads a .pem file\n"
            "6. Install the app on your repo: App settings → [bold]Install App[/bold] → select the repo",
            title="ℹ How to create a GitHub App",
            border_style="blue",
        ))

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
        default_key_path = "~/.sweat/github-app.pem"
        while True:
            key_path_str = typer.prompt("Path to private key (.pem file)", default=default_key_path)
            key_path = Path(os.path.expanduser(key_path_str))
            if not key_path.exists():
                console.print(f"[red]  ✗ File not found: {key_path}[/red]")
                continue
            github_private_key = key_path.read_text()
            if "BEGIN" not in github_private_key:
                console.print("[red]  ✗ File does not look like a PEM private key.[/red]")
                continue
            break
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
        github_env_lines = f"GITHUB_APP_ID={github_app_id}\nGITHUB_APP_PRIVATE_KEY_PATH={key_path_str}\n"

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

    console.print(Panel("[bold]Setup complete[/bold]"))
    console.print(env_msg)
    console.print(config_msg)
    console.print("\nNext steps:")
    console.print("  1. Review and customize sweat.config.json (field_names, field_filters, etc.)")
    console.print("  2. Run: sweat start")


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
    """Interactive setup: create .env and sweat.config.json."""
    _cmd_init()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
