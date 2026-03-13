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
                return False
        elif isinstance(condition, dict):
            if value is None:
                return False
            try:
                num = float(value)
            except (ValueError, TypeError):
                return False
            if "max" in condition and num > condition["max"]:
                return False
            if "min" in condition and num < condition["min"]:
                return False
    return True


def filter_and_rank_tasks(tasks: list[dict], project_cfg: dict) -> list[dict]:
    field_names = project_cfg.get("field_names", {})
    field_filters = project_cfg.get("field_filters", {})
    priority_order = project_cfg.get("priority_order", ["Urgent", "High", "Medium", "Low"])
    max_tasks = project_cfg.get("max_tasks_for_selector", 20)

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
