import json
import re


def _to_minutes(value: str) -> float | None:
    """Convert a duration string to minutes. Returns None if unparseable.

    Supports:
      - Plain numbers: "90" → 90.0
      - Hours + minutes: "2h 00m", "1h 30m" → 120.0, 90.0
      - Minutes only: "30m", "45m" → 30.0, 45.0
      - Hours only: "2h" → 120.0
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    if not isinstance(value, str):
        return None
    m = re.fullmatch(r"(?:(\d+)h\s*)?(?:(\d+)m)?", value.strip())
    if m and (m.group(1) or m.group(2)):
        hours = int(m.group(1) or 0)
        mins = int(m.group(2) or 0)
        return float(hours * 60 + mins)
    return None


def _extract_field(task: dict, field_name: str) -> str | None:
    for cf in task.get("custom_fields", []):
        if cf.get("name") == field_name:
            return cf.get("display_value")
    return None


def _passes_filters(task: dict, field_filters: dict, field_names: dict) -> bool:
    for key, condition in field_filters.items():
        field_name = field_names.get(key)
        if not field_name:
            continue
        value = _extract_field(task, field_name)
        if isinstance(condition, list):
            if value not in condition:
                print(
                    f"    skip [{task['name']}]: {field_name} = {value!r} not in {condition}"
                )
                return False
        elif isinstance(condition, dict):
            if value is None:
                print(f"    skip [{task['name']}]: {field_name} is missing")
                return False
            num = _to_minutes(value)
            if num is None:
                print(
                    f"    skip [{task['name']}]: {field_name} = {value!r} could not be parsed as a number or duration"
                )
                return False
            if "max" in condition and num > condition["max"]:
                print(
                    f"    skip [{task['name']}]: {field_name} = {num}m > max {condition['max']}m"
                )
                return False
            if "min" in condition and num < condition["min"]:
                print(
                    f"    skip [{task['name']}]: {field_name} = {num}m < min {condition['min']}m"
                )
                return False
    return True


def filter_and_rank_tasks(tasks: list[dict], project_cfg: dict) -> list[dict]:
    field_names = project_cfg.get("field_names", {})
    field_filters = project_cfg.get("field_filters", {})
    priority_order = project_cfg.get("priority_order", ["High", "Medium", "Low"])
    max_tasks = project_cfg.get("max_tasks_for_selector", 20)

    print(f"Config: {json.dumps(project_cfg, indent=2)}")

    if field_filters:
        tasks = [t for t in tasks if _passes_filters(t, field_filters, field_names)]

    priority_field = field_names.get("priority")
    if priority_field:

        def _priority_key(task):
            val = _extract_field(task, priority_field)
            try:
                return priority_order.index(val)
            except (ValueError, TypeError):
                return len(priority_order)

        tasks = sorted(tasks, key=_priority_key)

    return tasks[:max_tasks]
