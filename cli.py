"""
sweat CLI — start the background service.

Usage:
    uv run python cli.py start [--implement-interval 3600] [--review-interval 60]
    uv run python cli.py log [--last N]
"""
import argparse
import asyncio
import json
import logging
import os
import signal

import config
from main import run as run_implementer
from pr_poller import poll_and_review


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def _implementer_loop(interval: int) -> None:
    logging.info(f"Implementer loop started (every {interval}s)")
    while True:
        try:
            logging.info("Implementer: running")
            await run_implementer()
        except Exception as exc:
            logging.error(f"Implementer: error — {exc}")
        await asyncio.sleep(interval)


async def _reviewer_loop(interval: int) -> None:
    logging.info(f"Reviewer loop started (every {interval}s)")
    while True:
        try:
            await poll_and_review()
        except Exception as exc:
            logging.error(f"Reviewer: error — {exc}")
        await asyncio.sleep(interval)


async def _start(implement_interval: int, review_interval: int) -> None:
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set_result, None)

    logging.info("sweat service starting")
    tasks = [
        asyncio.create_task(_implementer_loop(implement_interval)),
        asyncio.create_task(_reviewer_loop(review_interval)),
    ]
    try:
        await stop
    finally:
        logging.info("sweat service shutting down")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def _format_log_entry(record: dict) -> str:
    ts = record.get("timestamp", "")[:19].replace("T", " ")
    event = record.get("event", "")
    repo = record.get("repo", "")
    repo_part = f"[{repo}] " if repo else ""

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
        detail = str({k: v for k, v in record.items() if k not in ("timestamp", "event", "repo")})

    return f"{ts}  {event:<30} {repo_part}{detail}"


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

    start = sub.add_parser("start", help="Start the sweat service")
    start.add_argument("--implement-interval", type=int, default=3600, metavar="SECONDS",
                       help="How often to run the implementer loop (default: 3600)")
    start.add_argument("--review-interval", type=int, default=60, metavar="SECONDS",
                       help="How often to run the PR reviewer loop (default: 60)")

    sub.add_parser("review", help="Run the PR reviewer once and exit")

    log_cmd = sub.add_parser("log", help="View recent audit log entries")
    log_cmd.add_argument("--last", type=int, default=20, metavar="N",
                         help="Number of recent entries to show (default: 20)")

    args = parser.parse_args()
    if args.command == "start":
        asyncio.run(_start(args.implement_interval, args.review_interval))
    elif args.command == "review":
        asyncio.run(poll_and_review())
    elif args.command == "log":
        _cmd_log(args.last)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
