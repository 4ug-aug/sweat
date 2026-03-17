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
- `pseudo_solution` (string) — 2–5 line plain-English or pseudo-code sketch of the fix. Newlines
  are represented as `\n` in JSON. Missing or empty values are allowed; treat as `""`.

Updated JSON schema example:
```json
{
  "title": "Remove unused imports in auth module",
  "category": "dead_code",
  "priority": "low",
  "description": "auth/utils.py lines 1-4 import `os` and `sys` which are never referenced, violating the no-dead-imports rule.",
  "estimated_minutes": 15,
  "pseudo_solution": "1. Scan imports in auth/\n2. Delete unused ones\n3. Run tests"
}
```

### 2. `clients/asana.py`

Update `create_task` and `create_task_async` to match these signatures:

```python
def create_task(
    self,
    project_id: str,
    name: str,
    notes: str = "",
    html_notes: str = "",
    estimated_minutes: int | None = None,
) -> dict

async def create_task_async(
    self,
    project_id: str,
    name: str,
    notes: str = "",
    html_notes: str = "",
    estimated_minutes: int | None = None,
) -> dict
```

Body construction rules:
- If `html_notes` is non-empty, include `html_notes` in the body and omit `notes`. (Asana treats the two as mutually exclusive; sending both is rejected.)
- If `html_notes` is empty, include `notes` in the body (even if empty, for backward compatibility).
- If `estimated_minutes` is not `None`, include `estimated_duration_minutes` in the body.

> **Note for implementer:** `estimated_duration_minutes` is used as a top-level task field in the
> Asana v5 REST API (not a custom field). Verify against the Asana SDK task model before shipping.
> If the field is rejected at runtime, the fallback is to include the estimate as text in the
> notes/html_notes instead.

### 3. `agents/code_reviewer.py`

Rename `_format_task_notes` → `_format_task_html`. There is exactly one call site (line 89).
No other callers exist — confirm with `grep` before renaming.

The function returns an HTML string. HTML-escape all user-supplied string values
(`html.escape(value)`) before inserting them into the template to prevent malformed HTML.
If `pseudo_solution` is missing or empty, omit the "Proposed Solution" section entirely.

Required HTML output structure (use this literally as the template):

```html
<body>
<p><strong>Category:</strong> {category} &nbsp;|&nbsp; <strong>Priority:</strong> {priority}<br/>
<strong>Repository:</strong> {repo}</p>
<p>{description}</p>
<p><strong>Proposed Solution</strong></p>
<pre><code>{pseudo_solution}</code></pre>
<hr/>
<em>Created by sweat code review agent</em>
</body>
```

The `<pre><code>` block preserves newlines in the pseudo solution. Omit it when `pseudo_solution`
is empty.

Update the call site in `run_once`:

```python
html_notes = _format_task_html(finding, repo)
await self.asana.create_task_async(
    project_id,
    finding["title"],
    html_notes=html_notes,
    estimated_minutes=finding.get("estimated_minutes"),
)
```

## Out of Scope

- Changing how many findings are created (still capped at 3).
- Any changes to the reviewer agent or implementer agent.
- Asana custom fields (estimated time uses the built-in `estimated_duration_minutes` field).

## Testing

### `tests/test_code_reviewer.py`

1. **`_parse_findings`** — update the shared `_SAMPLE_FINDINGS` module-level constant to include
   `estimated_minutes` and `pseudo_solution` on each finding. This constant is used by six tests;
   adding the new fields is backward-compatible and will not break them. Assert the new fields
   are present in the parsed output.
2. **`_format_task_html`** — add a new unit test for the function directly:
   - Assert output contains `<strong>`, `<pre><code>`, and the escaped field values.
   - Assert the "Proposed Solution" block is omitted when `pseudo_solution` is empty or missing.
   - Assert values are HTML-escaped (e.g. `<` becomes `&lt;`).
3. **`run_once` integration** — update existing test to assert that `create_task_async` is called
   with `html_notes=` (not `notes=`) and `estimated_minutes=` matching the fixture finding.

### `tests/test_asana_client.py`

1. **Existing `test_create_task_calls_api`** — update the assertion to match the new body
   construction logic (plain `notes` path, since no `html_notes` is passed).
2. **Add `test_create_task_with_html_notes`** — assert body contains `html_notes` and omits
   `notes` when `html_notes` is provided.
3. **Add `test_create_task_with_estimated_minutes`** — assert body contains
   `estimated_duration_minutes` when `estimated_minutes` is passed.
