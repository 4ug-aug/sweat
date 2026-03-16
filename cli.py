"""
sweat CLI — start the background service.

Usage:
    sweat start
    sweat review
    sweat log [--last N]
    sweat init
"""

import argparse
import asyncio
import getpass
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

import config
import telemetry


from agents.registry import AGENT_TYPES
from clients.asana import AsanaClient
from clients.github import GitHubClient


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
    if not config.ASANA_TOKEN or not config.GITHUB_TOKEN:
        logging.error(
            "ASANA_TOKEN and GITHUB_TOKEN must be set. Run 'sweat init' to configure."
        )
        return []
    if not config.AGENTS:
        logging.error(
            "No agents configured. Run 'sweat init' to create sweat.config.json."
        )
        return []

    github = GitHubClient(config.GITHUB_TOKEN)
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
            initial_delay = i * (interval / replicas) if replicas > 1 else 0
            agents.append((agent, interval, initial_delay))
    return agents


async def _agent_loop(agent, interval: int, initial_delay: float = 0) -> None:
    if initial_delay > 0:
        logging.info(
            f"Agent {agent.agent_id!r} waiting {initial_delay:.0f}s before first run"
        )
        await asyncio.sleep(initial_delay)
    logging.info(f"Agent {agent.agent_id!r} loop started (every {interval}s)")
    while True:
        tracer = telemetry.tracer()
        with tracer.start_as_current_span(
            "agent.run_once",
            attributes={
                "agent.id": agent.agent_id,
                "agent.type": agent.config.get("type", ""),
            },
        ) as span:
            try:
                logging.info(f"Agent {agent.agent_id!r}: running")
                if telemetry.agent_runs:
                    telemetry.agent_runs.add(1, {"agent.id": agent.agent_id})
                start = time.monotonic()
                await agent.run_once()
                if telemetry.agent_run_duration:
                    telemetry.agent_run_duration.record(
                        time.monotonic() - start, {"agent.id": agent.agent_id}
                    )
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
    tasks = [
        asyncio.create_task(_agent_loop(agent, interval, delay))
        for agent, interval, delay in agents
    ]
    try:
        await stop
    finally:
        logging.info("sweat service shutting down")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _run_once(type_filter: str) -> None:
    agents = _build_agents(type_filter=type_filter)
    for agent, _interval, _delay in agents:
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
    else:
        detail = str(
            {
                k: v
                for k, v in record.items()
                if k not in ("timestamp", "event", "repo", "agent_id")
            }
        )

    return f"{ts}  {agent_part}{event:<30} {repo_part}{detail}"


def _cmd_log(last: int) -> None:
    path = config.AUDIT_LOG_PATH
    if not os.path.exists(path):
        print(f"No audit log found at {path}")
        return
    with open(path) as f:
        lines = f.readlines()
    for line in lines[-last:]:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            print(_format_log_entry(record))
        except json.JSONDecodeError:
            print(line)


def _pick(items: list[dict], name_key: str, noun: str) -> dict:
    """Prompt user to select one item from a numbered list; defaults to first."""
    if len(items) == 1:
        print(f"Using {noun}: {items[0][name_key]}")
        return items[0]
    print(f"\nAvailable {noun}s:")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item[name_key]}")
    raw = input(f"Select {noun} [1]: ").strip()
    try:
        idx = int(raw) - 1 if raw else 0
    except ValueError:
        idx = 0
    return items[max(0, min(idx, len(items) - 1))]


def _cmd_init() -> None:
    """Interactive setup: validate credentials, discover config, write files."""
    print("sweat init — interactive setup\n")

    asana_token = getpass.getpass("Asana personal access token: ")
    github_token = getpass.getpass("GitHub personal access token: ")

    print("\nValidating tokens...")

    try:
        asana_client = AsanaClient(asana_token)
        me = asana_client.get_current_user()
        asana_assignee_gid = me["gid"]
        print(f"  Asana:  authenticated as {me['name']}")
    except Exception as exc:
        print(f"  Asana:  failed — {exc}")
        sys.exit(1)

    try:
        github_client = GitHubClient(github_token)
        gh_login = github_client.get_bot_login()
        print(f"  GitHub: authenticated as {gh_login}")
    except Exception:
        print("  GitHub: invalid token — check it and try again.")
        sys.exit(1)

    try:
        workspaces = asana_client.get_workspaces()
    except Exception:
        print("Failed to fetch Asana workspaces.")
        sys.exit(1)
    if not workspaces:
        print("No Asana workspaces found for this token.")
        sys.exit(1)
    workspace = _pick(workspaces, "name", "workspace")

    try:
        projects = asana_client.get_projects(workspace["gid"])
    except Exception:
        print(f"Failed to fetch projects for workspace '{workspace['name']}'.")
        sys.exit(1)
    if not projects:
        print(f"No projects found in workspace '{workspace['name']}'.")
        sys.exit(1)
    project = _pick(projects, "name", "project")
    asana_project_id = project["gid"]

    github_repo = input("\nGitHub repo (owner/name): ").strip()

    cwd = Path.cwd()

    # Write .env
    env_path = cwd / ".env"
    if not env_path.exists():
        env_path.write_text(f"ASANA_TOKEN={asana_token}\nGITHUB_TOKEN={github_token}\n")
        print(f"\nWrote {env_path}")
    else:
        print(f"\nSkipped {env_path} (already exists)")

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
        print(f"Wrote {config_path}")
    else:
        print(f"Skipped {config_path} (already exists)")

    print("\nNext steps:")
    print(
        "  1. Review and customize sweat.config.json (field_names, field_filters, etc.)"
    )
    print("  2. Run: sweat-agent start")


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(
        prog="sweat", description="sweat — agentic software engineer service"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Start all configured agents")

    sub.add_parser("review", help="Run reviewer agents once and exit")

    sub.add_parser("code-review", help="Run code review agents once and exit")

    log_cmd = sub.add_parser("log", help="View recent audit log entries")
    log_cmd.add_argument(
        "--last",
        type=int,
        default=20,
        metavar="N",
        help="Number of recent entries to show (default: 20)",
    )

    sub.add_parser(
        "init",
        help="Interactive setup: create .env and sweat.config.json",
    )

    args = parser.parse_args()
    if args.command == "start":
        telemetry.init()
        asyncio.run(_start())
    elif args.command == "review":
        asyncio.run(_run_once("reviewer"))
    elif args.command == "code-review":
        asyncio.run(_run_once("code_reviewer"))
    elif args.command == "log":
        _cmd_log(args.last)
    elif args.command == "init":
        _cmd_init()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
