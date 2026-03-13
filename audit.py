import json
from datetime import datetime, timezone

import config


def log_event(event: str, agent_id: str | None = None, **data) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **data}
    if agent_id:
        record["agent_id"] = agent_id
    with open(config.AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
