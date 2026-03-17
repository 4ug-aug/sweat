# Code Reviewer Task Formatting Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve code reviewer Asana task quality by adding HTML-formatted notes, a proper estimated time field, and a pseudo solution for each finding.

**Architecture:** Three focused changes across three files: (1) extend the Asana client to accept `html_notes` and `estimated_minutes`, (2) extend the LLM prompt to request the two new JSON fields, (3) replace the plain-text formatter in the agent with an HTML formatter and thread the new values through to the API call.

**Tech Stack:** Python, Asana v5 SDK (`asana`), `html` stdlib for escaping, `asyncio.to_thread` for async wrapping.

**Spec:** `docs/superpowers/specs/2026-03-17-code-reviewer-task-formatting-design.md`

---

## Chunk 1: Extend AsanaClient to support html_notes and estimated_minutes

**Files:**
- Modify: `clients/asana.py:184-222`
- Modify: `tests/test_asana_client.py:113-125`

### Task 1: Update AsanaClient.create_task and create_task_async

- [ ] **Step 1: Write failing test — html_notes excludes notes from body**

  Add to `tests/test_asana_client.py`:

  ```python
  @patch("clients.asana._Client")
  def test_create_task_with_html_notes(mock_client_class):
      mock_client = MagicMock()
      mock_client_class.return_value = mock_client
      mock_client.tasks.create_task.return_value = {"gid": "999", "name": "Task"}

      client = AsanaClient("test-token")
      client.create_task("PROJECT_GID", "Task", html_notes="<body>content</body>")

      call_body = mock_client.tasks.create_task.call_args[0][0]
      assert call_body["html_notes"] == "<body>content</body>"
      assert "notes" not in call_body
  ```

- [ ] **Step 2: Run test to confirm it fails**

  ```
  uv run pytest tests/test_asana_client.py::test_create_task_with_html_notes -v
  ```
  Expected: FAIL — `create_task()` got unexpected keyword argument `html_notes`

- [ ] **Step 3: Write failing test — estimated_minutes sets estimated_duration_minutes**

  Add to `tests/test_asana_client.py`:

  ```python
  @patch("clients.asana._Client")
  def test_create_task_with_estimated_minutes(mock_client_class):
      mock_client = MagicMock()
      mock_client_class.return_value = mock_client
      mock_client.tasks.create_task.return_value = {"gid": "999", "name": "Task"}

      client = AsanaClient("test-token")
      client.create_task("PROJECT_GID", "Task", estimated_minutes=60)

      call_body = mock_client.tasks.create_task.call_args[0][0]
      assert call_body["estimated_duration_minutes"] == 60
  ```

- [ ] **Step 4: Run test to confirm it fails**

  ```
  uv run pytest tests/test_asana_client.py::test_create_task_with_estimated_minutes -v
  ```
  Expected: FAIL

- [ ] **Step 5: Implement the changes in `clients/asana.py`**

  Replace `create_task` (lines 184-190) and `create_task_async` (lines 221-222) with:

  ```python
  def create_task(
      self,
      project_id: str,
      name: str,
      notes: str = "",
      html_notes: str = "",
      estimated_minutes: int | None = None,
  ) -> dict:
      try:
          body = {"name": name, "projects": [project_id]}
          if html_notes:
              body["html_notes"] = html_notes
          else:
              body["notes"] = notes
          if estimated_minutes is not None:
              body["estimated_duration_minutes"] = estimated_minutes
          result = self._client.tasks.create_task(body)
          return result
      except Exception as exc:
          raise AsanaError(f"Failed to create task in project {project_id}: {exc}") from exc

  async def create_task_async(
      self,
      project_id: str,
      name: str,
      notes: str = "",
      html_notes: str = "",
      estimated_minutes: int | None = None,
  ) -> dict:
      return await asyncio.to_thread(
          self.create_task,
          project_id,
          name,
          notes=notes,
          html_notes=html_notes,
          estimated_minutes=estimated_minutes,
      )
  ```

- [ ] **Step 6: Write test for `create_task_async` with new parameters**

  Add to `tests/test_asana_client.py`:

  ```python
  @patch("clients.asana._Client")
  async def test_create_task_async_forwards_html_notes_and_estimated_minutes(mock_client_class):
      mock_client = MagicMock()
      mock_client_class.return_value = mock_client
      mock_client.tasks.create_task.return_value = {"gid": "999", "name": "Task"}

      client = AsanaClient("test-token")
      await client.create_task_async(
          "PROJECT_GID", "Task", html_notes="<body>html</body>", estimated_minutes=45
      )

      call_body = mock_client.tasks.create_task.call_args[0][0]
      assert call_body["html_notes"] == "<body>html</body>"
      assert "notes" not in call_body
      assert call_body["estimated_duration_minutes"] == 45
  ```

- [ ] **Step 7: Run all new and existing asana client tests**

  ```
  uv run pytest tests/test_asana_client.py -v
  ```
  Expected: All PASS. Note: `test_create_task_calls_api` requires no change — calling with
  positional `notes="Some notes"` still falls through the `else` branch and produces the same
  body dict.

- [ ] **Step 8: Commit**

  ```bash
  git add clients/asana.py tests/test_asana_client.py
  git commit -m "feat: support html_notes and estimated_minutes in AsanaClient.create_task"
  ```

---

## Chunk 2: Extend the code review prompt with new JSON fields

**Files:**
- Modify: `prompts/code_review_prompt.py`

### Task 2: Add estimated_minutes and pseudo_solution to the LLM JSON schema

- [ ] **Step 1: Update `_SAMPLE_FINDINGS` in `tests/test_code_reviewer.py`**

  The constant at line 24 is shared by six tests. Adding the new fields is backward-compatible.
  Replace the `_SAMPLE_FINDINGS` constant with:

  ```python
  _SAMPLE_FINDINGS = json.dumps(
      {
          "findings": [
              {
                  "title": "Inconsistent error handling in API layer",
                  "category": "inconsistent_pattern",
                  "priority": "high",
                  "description": "api/handlers.py uses mixed patterns",
                  "estimated_minutes": 30,
                  "pseudo_solution": "1. Standardize exception handling\n2. Add error middleware",
              },
              {
                  "title": "Dead import in utils module",
                  "category": "dead_code",
                  "priority": "medium",
                  "description": "utils/helpers.py:3 imports unused os module",
                  "estimated_minutes": 10,
                  "pseudo_solution": "1. Remove unused import\n2. Run tests",
              },
              {
                  "title": "Complex validation function",
                  "category": "complexity",
                  "priority": "low",
                  "description": "validators.py:45 has cyclomatic complexity of 15",
                  "estimated_minutes": 60,
                  "pseudo_solution": "1. Split into smaller functions\n2. Write unit tests",
              },
          ]
      }
  )
  ```

- [ ] **Step 2: Extend `test_parse_findings_plain_json` to assert the new fields**

  Update the existing test (line 180) to also assert:

  ```python
  def test_parse_findings_plain_json():
      findings = _parse_findings(_SAMPLE_FINDINGS)
      assert len(findings) == 3
      assert findings[0]["title"] == "Inconsistent error handling in API layer"
      assert findings[0]["estimated_minutes"] == 30
      assert "pseudo_solution" in findings[0]
  ```

- [ ] **Step 3: Run existing parse tests to confirm they still pass**

  ```
  uv run pytest tests/test_code_reviewer.py::test_parse_findings_plain_json tests/test_code_reviewer.py::test_parse_findings_markdown_fenced tests/test_code_reviewer.py::test_parse_findings_empty -v
  ```
  Expected: All PASS (no code change yet; the fields are just new keys in the fixture)

- [ ] **Step 4: Update `prompts/code_review_prompt.py`**

  Replace the entire file with:

  ```python
  def build_code_review_prompt(quality_doc: str, repo: str) -> str:
      return f"""You are a senior software engineer performing a code quality review of the repository `{repo}`.

  ## Quality Standards

  The following document defines the quality standards for this codebase:

  {quality_doc}

  ## Instructions

  Scan the repository for code quality issues. Focus on:
  - Inconsistent patterns (naming, error handling, structure)
  - Dead code (unused imports, unreachable branches, deprecated functions)
  - Complex functions (high cyclomatic complexity, deep nesting, long methods)

  Trace each finding back to a specific principle in the quality standards document above.
  Reference specific files and line numbers for each finding.

  For each finding also provide:
  - A realistic estimate of how many minutes it would take a developer to fix it (`estimated_minutes`, integer).
  - A brief 2-5 step pseudo-code or plain-English sketch of how to fix it (`pseudo_solution`, string, use \\n between steps).

  Respond ONLY with valid JSON in this exact format — no markdown fences, no extra text:
  {{"findings": [{{"title": "Short descriptive title", "category": "inconsistent_pattern|dead_code|complexity", "priority": "low|medium|high", "description": "Detailed description referencing specific files/lines and the quality principle violated", "estimated_minutes": 30, "pseudo_solution": "1. Do this\\n2. Then that"}}]}}

  Return exactly 3 findings, ranked by priority (highest first). If fewer than 3 issues exist, return as many as you find."""
  ```

- [ ] **Step 5: Run all code reviewer tests**

  ```
  uv run pytest tests/test_code_reviewer.py -v
  ```
  Expected: All PASS

- [ ] **Step 6: Commit**

  ```bash
  git add prompts/code_review_prompt.py tests/test_code_reviewer.py
  git commit -m "feat: add estimated_minutes and pseudo_solution to code review prompt"
  ```

---

## Chunk 3: Replace plain-text formatter with HTML formatter in the agent

> **Depends on Chunk 1.** `AsanaClient.create_task_async` must already accept `html_notes=` and
> `estimated_minutes=` (done in Chunk 1) before this chunk's call-site change and mock assertions
> will work.

**Files:**
- Modify: `agents/code_reviewer.py:89-90,144-151`
- Modify: `tests/test_code_reviewer.py` (add imports + new tests)

### Task 3: Implement _format_task_html and update the call site

- [ ] **Step 1: Add `_format_task_html` to the import in the test file**

  In `tests/test_code_reviewer.py` line 8, add `_format_task_html` to the import:

  ```python
  from agents.code_reviewer import CodeReviewerAgent, _format_task_html, _is_duplicate, _parse_findings
  ```

- [ ] **Step 2: Write failing tests for `_format_task_html`**

  Add these tests at the end of `tests/test_code_reviewer.py`:

  ```python
  # --- Unit tests for _format_task_html ---


  def test_format_task_html_contains_metadata():
      finding = {
          "category": "dead_code",
          "priority": "high",
          "description": "Some description",
          "pseudo_solution": "1. Fix it\n2. Test it",
      }
      result = _format_task_html(finding, "org/repo")
      assert "<strong>Category:</strong>" in result
      assert "dead_code" in result
      assert "<strong>Priority:</strong>" in result
      assert "high" in result
      assert "org/repo" in result
      assert "<pre><code>" in result
      assert "1. Fix it" in result


  def test_format_task_html_omits_solution_when_empty():
      finding = {
          "category": "dead_code",
          "priority": "low",
          "description": "Something",
          "pseudo_solution": "",
      }
      result = _format_task_html(finding, "org/repo")
      assert "<pre><code>" not in result
      assert "Proposed Solution" not in result


  def test_format_task_html_omits_solution_when_missing():
      finding = {
          "category": "dead_code",
          "priority": "low",
          "description": "Something",
      }
      result = _format_task_html(finding, "org/repo")
      assert "<pre><code>" not in result


  def test_format_task_html_escapes_values():
      finding = {
          "category": "<script>",
          "priority": "low",
          "description": "A & B",
          "pseudo_solution": "x < y",
      }
      result = _format_task_html(finding, "org/repo")
      assert "<script>" not in result
      assert "&lt;script&gt;" in result
      assert "&amp;" in result
      assert "&lt;" in result
  ```

- [ ] **Step 3: Run new tests to confirm they fail**

  ```
  uv run pytest tests/test_code_reviewer.py::test_format_task_html_contains_metadata -v
  ```
  Expected: FAIL — `ImportError: cannot import name '_format_task_html'`

- [ ] **Step 4: Write failing integration test for html_notes call site**

  Add to `tests/test_code_reviewer.py`:

  ```python
  @patch("agents.code_reviewer.run_agent", new_callable=AsyncMock)
  @patch("agents.code_reviewer.shutil.rmtree")
  async def test_full_flow_passes_html_notes_and_estimated_minutes(mock_rmtree, mock_run_agent, tmp_path):
      agent = _make_agent()
      repo_path = str(tmp_path)
      agent.github.clone_repo_async.return_value = repo_path

      doc_path = tmp_path / "docs" / "code-quality.md"
      doc_path.parent.mkdir(parents=True)
      doc_path.write_text("# Quality Standards\nKeep it clean.")

      mock_run_agent.return_value = AgentResult(success=True, summary=_SAMPLE_FINDINGS)
      agent.asana.get_tasks_async.return_value = []

      await agent.run_once()

      first_call_kwargs = agent.asana.create_task_async.call_args_list[0].kwargs
      assert "html_notes" in first_call_kwargs
      assert "<strong>" in first_call_kwargs["html_notes"]
      assert first_call_kwargs.get("estimated_minutes") == 30
  ```

  Run this test to confirm it fails:
  ```
  uv run pytest tests/test_code_reviewer.py::test_full_flow_passes_html_notes_and_estimated_minutes -v
  ```
  Expected: FAIL — `ImportError` (Step 1 import not resolved yet) or assertion failure on
  `"html_notes" in first_call_kwargs` (the old call site passes notes positionally, so kwargs is
  empty). This test becomes green only after both Step 5 (implement `_format_task_html`) and
  Step 6 (update call site) are complete.

- [ ] **Step 5: Implement `_format_task_html` in `agents/code_reviewer.py`**

  Add `import html as _html` to the top-level imports (after `import os`).

  Replace the `_format_task_notes` function (lines 144-151) with:

  ```python
  def _format_task_html(finding: dict, repo: str) -> str:
      category = _html.escape(finding.get("category", "N/A"))
      priority = _html.escape(finding.get("priority", "N/A"))
      repo_escaped = _html.escape(repo)
      description = _html.escape(finding.get("description", ""))
      pseudo_solution = finding.get("pseudo_solution", "")

      solution_html = ""
      if pseudo_solution:
          solution_html = (
              f"<p><strong>Proposed Solution</strong></p>"
              f"<pre><code>{_html.escape(pseudo_solution)}</code></pre>"
          )

      return (
          f"<body>"
          f"<p><strong>Category:</strong> {category} &nbsp;|&nbsp; "
          f"<strong>Priority:</strong> {priority}<br/>"
          f"<strong>Repository:</strong> {repo_escaped}</p>"
          f"<p>{description}</p>"
          f"{solution_html}"
          f"<hr/>"
          f"<em>Created by sweat code review agent</em>"
          f"</body>"
      )
  ```

- [ ] **Step 6: Update the call site in `run_once` (line 89-90)**

  Replace:
  ```python
  notes = _format_task_notes(finding, repo)
  await self.asana.create_task_async(project_id, finding["title"], notes)
  ```
  With:
  ```python
  html_notes = _format_task_html(finding, repo)
  await self.asana.create_task_async(
      project_id,
      finding["title"],
      html_notes=html_notes,
      estimated_minutes=finding.get("estimated_minutes"),
  )
  ```

- [ ] **Step 7: Run all tests**

  ```
  uv run pytest tests/test_code_reviewer.py -v
  ```
  Expected: All PASS

- [ ] **Step 8: Run the full test suite**

  ```
  uv run pytest -v
  ```
  Expected: All PASS

- [ ] **Step 9: Commit**

  ```bash
  git add agents/code_reviewer.py tests/test_code_reviewer.py
  git commit -m "feat: format code review tasks as HTML with pseudo solution and estimated time"
  ```
