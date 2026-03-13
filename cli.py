"""
sweat CLI — start the background service.

Usage:
    uv run python cli.py start
    uv run python cli.py review
    uv run python cli.py log [--last N]
"""
import argparse
import asyncio
import json
import logging
import os
import signal

import config
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
        logging.info(f"Agent {agent.agent_id!r} waiting {initial_delay:.0f}s before first run")
        await asyncio.sleep(initial_delay)
    logging.info(f"Agent {agent.agent_id!r} loop started (every {interval}s)")
    while True:
        try:
            logging.info(f"Agent {agent.agent_id!r}: running")
            await agent.run_once()
        except Exception as exc:
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
    tasks = [asyncio.create_task(_agent_loop(agent, interval, delay)) for agent, interval, delay in agents]
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
    else:
        detail = str({k: v for k, v in record.items() if k not in ("timestamp", "event", "repo", "agent_id")})

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


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(prog="sweat", description="sweat — agentic software engineer service")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Start all configured agents")

    sub.add_parser("review", help="Run reviewer agents once and exit")

    log_cmd = sub.add_parser("log", help="View recent audit log entries")
    log_cmd.add_argument("--last", type=int, default=20, metavar="N",
                         help="Number of recent entries to show (default: 20)")

    args = parser.parse_args()
    if args.command == "start":
        asyncio.run(_start())
    elif args.command == "review":
        asyncio.run(_run_once("reviewer"))
    elif args.command == "log":
        _cmd_log(args.last)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
