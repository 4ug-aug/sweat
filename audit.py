import json
from datetime import datetime, timezone

from opentelemetry import trace

import config
import telemetry


def log_event(event: str, agent_id: str | None = None, **data) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **data}
    if agent_id:
        record["agent_id"] = agent_id
    with open(config.AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")

    # Attach as span event on current trace + bump metrics
    span = trace.get_current_span()
    if span.is_recording():
        attrs = {"audit.event": event}
        if agent_id:
            attrs["audit.agent_id"] = agent_id
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool)):
                attrs[f"audit.{k}"] = v
        span.add_event("audit", attributes=attrs)

    if event == "implementation_succeeded" and telemetry.tasks_implemented:
        telemetry.tasks_implemented.add(1)
    if event == "implementation_succeeded" and telemetry.prs_opened:
        telemetry.prs_opened.add(1)
    if event == "pr_review_posted" and telemetry.prs_reviewed:
        telemetry.prs_reviewed.add(1)
