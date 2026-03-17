# Code Reviewer Task Formatting — Design Spec

**Date:** 2026-03-17
**Status:** Approved

## Problem

The `CodeReviewerAgent` creates Asana tasks with flat plain-text notes (no visual hierarchy), no estimated time field, and no proposed fix. This makes the tasks hard to act on.

## Goals

1. Format task notes using Asana rich text (`html_notes`) for readable structure.
2. Set the Asana `estimated_duration_minutes` field on each created task.
3. Include a brief pseudo solution in each task so engineers know where to start.

## Changes

### 1. `prompts/code_review_prompt.py`

Add two fields to the JSON schema Claude must return:

- `estimated_minutes` (integer) — realistic time to fix the issue in minutes.
- `pseudo_solution` (string) — 2–5 line plain-English or pseudo-code sketch of the fix.

Example finding:
```json
{
  "title": "Remove unused imports in auth module",
  "category": "dead_code",
  "priority": "low",
  "description": "...",
  "estimated_minutes": 15,
  "pseudo_solution": "1. Scan imports in auth/\n2. Delete unused ones\n3. Run tests"
}
```

### 2. `clients/asana.py`

Update `create_task` and `create_task_async` signatures:

```python
def create_task(
    self,
    project_id: str,
    name: str,
    notes: str = "",
    html_notes: str = "",
    estimated_minutes: int | None = None,
) -> dict
```

- If `html_notes` is provided, send it instead of `notes`.
- If `estimated_minutes` is provided, include `estimated_duration_minutes` in the task body.

### 3. `agents/code_reviewer.py`

- Rename `_format_task_notes` → `_format_task_html`, returning an HTML string structured as:
  - Bold metadata line (category, priority, repo)
  - Description paragraph
  - "Proposed Solution" section with the pseudo solution in a `<code>` block
  - Footer line
- Update the `create_task_async` call site to pass `html_notes=` and `estimated_minutes=`.

## Out of Scope

- Changing how many findings are created (still capped at 3).
- Any changes to the reviewer agent or implementer agent.
- Asana custom fields (estimated time uses the built-in `estimated_duration_minutes` field).

## Testing

- Update `tests/test_code_reviewer.py` to assert `html_notes` is passed (not `notes`) and that `estimated_minutes` flows through to `create_task_async`.
- Update `tests/test_code_reviewer.py` `_parse_findings` tests to include the new fields.
- No changes needed to `tests/test_asana_client.py` beyond verifying the new optional params.
