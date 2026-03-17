import json
import fcntl
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(".sweat")
STATE_FILE = STATE_DIR / "agent_states.json"


def write_agent_state(
    agent_id: str,
    status: str,
    loop_name: str,
    last_error: str | None = None,
) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    states = read_all_states()
    states[agent_id] = {
        "status": status,
        "loop_name": loop_name,
        "last_run": datetime.now(timezone.utc).isoformat(),
        "last_error": last_error,
    }
    with open(STATE_FILE, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(states, f, indent=2)
        fcntl.flock(f, fcntl.LOCK_UN)


def read_all_states() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
