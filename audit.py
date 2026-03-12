import json
from datetime import datetime, timezone

import config


def log_event(event: str, **data) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **data}
    with open(config.AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
