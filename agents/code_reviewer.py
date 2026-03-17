import difflib
import html as _html
import json
import logging
import os
import shutil

import audit
from agent import AgentResult, run_agent
from agents.base import BaseAgent
from exceptions import AgentError
from prompts.code_review_prompt import build_code_review_prompt


class CodeReviewerAgent(BaseAgent):
    @property
    def default_interval(self) -> int:
        return 86400

    async def run_once(self) -> None:
        projects = self.config.get("projects", [])
        for project in projects:
            repo = project["github_repo"]
            project_id = project["asana_project_id"]
            quality_doc_path = project.get("quality_doc_path", "docs/code-quality.md")
            repo_path = None
            try:
                repo_path = await self.github.clone_repo_async(repo)
                quality_doc_file = os.path.join(repo_path, quality_doc_path)
                if not os.path.exists(quality_doc_file):
                    logging.warning(
                        f"[{self.agent_id}] Quality doc not found at {quality_doc_path} in {repo}, skipping"
                    )
                    audit.log_event(
                        "code_review_skipped",
                        agent_id=self.agent_id,
                        repo=repo,
                        reason="quality_doc_missing",
                    )
                    continue

                with open(quality_doc_file) as f:
                    quality_doc = f.read()

                prompt = build_code_review_prompt(quality_doc, repo)
                try:
                    result = await run_agent(repo_path, prompt)
                except AgentError as exc:
                    result = AgentResult(success=False, error=str(exc))

                if not result.success:
                    logging.warning(
                        f"[{self.agent_id}] Code review agent failed for {repo}: {result.error}"
                    )
                    audit.log_event(
                        "code_review_failed",
                        agent_id=self.agent_id,
                        repo=repo,
                        error=result.error,
                    )
                    continue

                findings = _parse_findings(result.summary)
                if not findings:
                    logging.warning(f"[{self.agent_id}] No valid findings parsed for {repo}")
                    audit.log_event(
                        "code_review_failed",
                        agent_id=self.agent_id,
                        repo=repo,
                        error="no_valid_findings",
                    )
                    continue

                existing_tasks = await self.asana.get_tasks_async(project_id)
                existing_titles = [t["name"] for t in existing_tasks]

                created = 0
                for finding in findings[:3]:
                    if _is_duplicate(finding["title"], existing_titles):
                        logging.info(
                            f"[{self.agent_id}] Duplicate skipped: {finding['title']}"
                        )
                        audit.log_event(
                            "code_review_duplicate_skipped",
                            agent_id=self.agent_id,
                            repo=repo,
                            title=finding["title"],
                        )
                        continue
                    html_notes = _format_task_html(finding, repo)
                    await self.asana.create_task_async(
                        project_id,
                        finding["title"],
                        html_notes=html_notes,
                        estimated_minutes=finding.get("estimated_minutes"),
                    )
                    created += 1
                    audit.log_event(
                        "code_review_task_created",
                        agent_id=self.agent_id,
                        repo=repo,
                        title=finding["title"],
                        category=finding.get("category", ""),
                        priority=finding.get("priority", ""),
                    )

                logging.info(
                    f"[{self.agent_id}] Code review complete for {repo}: "
                    f"{len(findings)} findings, {created} tasks created"
                )
                audit.log_event(
                    "code_review_completed",
                    agent_id=self.agent_id,
                    repo=repo,
                    findings_count=len(findings),
                    tasks_created=created,
                )
            finally:
                if repo_path:
                    shutil.rmtree(repo_path, ignore_errors=True)


def _parse_findings(summary: str) -> list[dict]:
    if not summary:
        return []
    text = summary
    if "```" in text:
        text = text.split("```")[1]
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # JSON may be truncated — try to salvage complete finding objects
        findings = _extract_partial_findings(text)
        if findings:
            logging.warning(
                f"Code review: JSON truncated, recovered {len(findings)} finding(s): {text[:200]}"
            )
            return findings
        logging.error(f"Code review: failed to parse JSON: {text[:200]}")
        return []
    if isinstance(data, dict) and "findings" in data:
        return data["findings"]
    return []


def _extract_partial_findings(text: str) -> list[dict]:
    """Extract complete JSON objects from a truncated findings array."""
    findings = []
    depth = 0
    start = None
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2  # skip escaped character
                continue
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        obj = json.loads(text[start : i + 1])
                        if isinstance(obj, dict) and "title" in obj:
                            findings.append(obj)
                    except json.JSONDecodeError:
                        pass
                    start = None
        i += 1
    return findings


def _is_duplicate(title: str, existing_titles: list[str]) -> bool:
    for existing in existing_titles:
        ratio = difflib.SequenceMatcher(None, title.lower(), existing.lower()).ratio()
        if ratio >= 0.8:
            return True
    return False


def _format_task_html(finding: dict, repo: str) -> str:
    category = _html.escape(finding.get("category", "N/A"))
    priority = _html.escape(finding.get("priority", "N/A"))
    repo_escaped = _html.escape(repo)
    description = _html.escape(finding.get("description", ""))
    pseudo_solution = finding.get("pseudo_solution", "")

    solution_html = ""
    if pseudo_solution:
        solution_html = (
            f"<strong>Proposed Solution</strong>"
            f"<pre>{_html.escape(pseudo_solution)}</pre>"
        )

    return (
        f"<body>"
        f"<ul>"
        f"<li><strong>Category:</strong> {category} | <strong>Priority:</strong> {priority}</li>"
        f"<li><strong>Repository:</strong> {repo_escaped}</li>"
        f"</ul>"
        f"{description}"
        f"{solution_html}"
        f"<hr/>"
        f"<em>Created by sweat code review agent</em>"
        f"</body>"
    )
