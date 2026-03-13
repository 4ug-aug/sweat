# Task Filtering & Ranking

SWEAT fetches all unassigned tasks from each Asana project, then filters and ranks them locally before passing a short, high-quality shortlist to Claude. This keeps token usage low and gives Claude better signal.

The pipeline is:

```
fetch all unassigned tasks
        ↓
hard filter  (drop tasks that don't match every condition)
        ↓
sort by priority
        ↓
cap at max_tasks_for_selector
        ↓
Claude picks one
```

---

## Configuration

All filtering is configured per-project in `config.py`. Every key below is optional — if omitted, that step is skipped and the raw task list is passed through unchanged.

```python
PROJECTS = [
    {
        "asana_project_id": "...",
        "github_repo": "org/repo",
        "branch_prefix": "agent/",

        # Maps logical field keys to the exact Asana custom field names
        # as they appear in your project. Only fields listed here are used.
        "field_names": {
            "priority":       "Priority",
            "estimated_time": "Estimated Time",
            "work_type":      "Work Type",
            "domain":         "Domain",
        },

        # Hard filters — tasks must pass ALL conditions to be included.
        # Keys must match keys in field_names above.
        "field_filters": {
            "work_type":      ["Bug", "Chore"],    # enum: value must be in list
            "domain":         ["Backend"],
            "estimated_time": {"max": 4},          # numeric: ≤ 4
            "priority":       {"min": 1, "max": 3} # numeric range
        },

        # Defines the sort order for the priority field (highest first).
        "priority_order": ["Urgent", "High", "Medium", "Low"],

        # Maximum number of tasks passed to Claude after filtering.
        "max_tasks_for_selector": 15,
    }
]
```

---

## Field names

`field_names` maps a fixed set of logical keys to the exact display names of your Asana custom fields. The names are case-sensitive and must match what Asana shows in the UI.

| Key | Used for |
|---|---|
| `priority` | Sorting tasks (uses `priority_order`) |
| `estimated_time` | Numeric range filters |
| `work_type` | Enum filters |
| `domain` | Enum filters |

You only need to list fields you actually use in `field_filters` or want surfaced in Claude's prompt. Unlisted fields are ignored.

---

## Filters

`field_filters` drops tasks before Claude sees them. Every condition must pass — it is a logical AND across all keys.

### Enum filter

```python
"work_type": ["Bug", "Chore"]
```

Keeps tasks where the field's value is one of the listed strings. Tasks where the field is absent or has any other value are dropped.

### Numeric filter

```python
"estimated_time": {"max": 4}
"estimated_time": {"min": 1, "max": 4}
```

Parses the field's display value as a float and compares it. Tasks where the field is absent, empty, or non-numeric (e.g. `"M"`, `"TBD"`) are dropped.

Supported keys: `min`, `max`.

---

## Priority sorting

After filtering, tasks are sorted by the field mapped to `priority`, using the order defined in `priority_order`:

```python
"priority_order": ["Urgent", "High", "Medium", "Low"]
```

Tasks with a priority value not in the list, or with no priority field, are sorted to the bottom. The sort is stable, so tasks with the same priority keep their original relative order.

---

## Cap

`max_tasks_for_selector` limits how many tasks are passed to Claude. After filtering and sorting, only the first N tasks (by priority) are used.

Default: `20` if omitted.

---

## How custom fields appear in Claude's prompt

Each task is formatted as a single line including any metadata found:

```
- GID: 123 | Name: Fix login crash | Priority: High | Est: 2 | Type: Bug | Domain: Backend | Notes: ...
```

Fields with no value are omitted from the line.

---

## Finding your Asana field names

The easiest way is to open a task in Asana and check the exact label shown next to each custom field. Alternatively, you can inspect the raw API response:

```bash
uv run python - <<'EOF'
import asana, config

cfg = asana.Configuration()
cfg.access_token = config.ASANA_TOKEN
api = asana.TasksApi(asana.ApiClient(cfg))

# Replace with any task GID from your project
task = api.get_task("YOUR_TASK_GID", {"opt_fields": "custom_fields"})
for cf in task["custom_fields"]:
    print(cf["name"], "→", cf.get("display_value"))
EOF
```

Use the printed names verbatim in `field_names`.
