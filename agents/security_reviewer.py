import difflib
import html as _html
import json
import logging
import shutil

import audit
from agent import AgentResult, run_agent
from agents.base import BaseAgent
from exceptions import AgentError
from prompts.security_review_prompt import build_security_review_prompt

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


class SecurityReviewerAgent(BaseAgent):
    @property
    def default_interval(self) -> int:
        return 86400

    async def run_once(self) -> None:
        projects = self.config.get("projects", [])
        skill_name = "security_reviewer"
        for project in projects:
            repo = project["github_repo"]
            project_id = project["asana_project_id"]
            repo_path = None
            try:
                repo_path = await self.github.clone_repo_async(repo)
                logging.info(
                    f"[{self.agent_id}] Using skill '{skill_name}' for {repo}"
                )
                audit.log_event(
                    "skills_applied",
                    agent_id=self.agent_id,
                    repo=repo,
                    skills=skill_name,
                )
                prompt = build_security_review_prompt(repo)
                try:
                    result = await run_agent(repo_path, prompt)
                except AgentError as exc:
                    result = AgentResult(success=False, error=str(exc))

                if not result.success:
                    logging.warning(
                        f"[{self.agent_id}] Security review agent failed for {repo}: {result.error}"
                    )
                    audit.log_event(
                        "security_review_failed",
                        agent_id=self.agent_id,
                        repo=repo,
                        error=result.error,
                    )
                    continue

                findings = _parse_findings(result.summary)
                if not findings:
                    logging.warning(f"[{self.agent_id}] No valid findings parsed for {repo}")
                    audit.log_event(
                        "security_review_failed",
                        agent_id=self.agent_id,
                        repo=repo,
                        error="no_valid_findings",
                    )
                    continue

                findings.sort(key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "INFO"), 99))

                existing_tasks = await self.asana.get_tasks_async(project_id)
                existing_titles = [t["name"] for t in existing_tasks]

                max_tasks = self.config.get("max_tasks_per_run", 3)
                created = 0
                for finding in findings[:max_tasks]:
                    if _is_duplicate(finding["title"], existing_titles):
                        logging.info(
                            f"[{self.agent_id}] Duplicate skipped: {finding['title']}"
                        )
                        audit.log_event(
                            "security_review_duplicate_skipped",
                            agent_id=self.agent_id,
                            repo=repo,
                            title=finding["title"],
                        )
                        continue
                    html_notes = _format_task_html(finding, repo)
                    await self.asana.create_task_async(
                        project_id,
                        f"[Security] {finding['title']}",
                        html_notes=html_notes,
                        estimated_minutes=finding.get("estimated_minutes"),
                    )
                    created += 1
                    audit.log_event(
                        "security_review_task_created",
                        agent_id=self.agent_id,
                        repo=repo,
                        title=finding["title"],
                        severity=finding.get("severity", ""),
                        category=finding.get("category", ""),
                    )

                logging.info(
                    f"[{self.agent_id}] Security review complete for {repo}: "
                    f"{len(findings)} findings, {created} tasks created"
                )
                audit.log_event(
                    "security_review_completed",
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

    text = summary.strip()
    for candidate in _json_candidates(text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        findings = _findings_from_data(data)
        if findings:
            return findings

    findings = _extract_partial_findings(text)
    if findings:
        logging.warning(
            f"Security review: JSON truncated, recovered {len(findings)} finding(s): {text[:200]}"
        )
        return findings
    logging.error(f"Security review: failed to parse JSON: {text[:200]}")
    return []


def _findings_from_data(data: object) -> list[dict]:
    if not isinstance(data, dict):
        return []
    findings = data.get("findings")
    if not isinstance(findings, list):
        return []
    return [item for item in findings if isinstance(item, dict) and item.get("title")]


def _json_candidates(text: str) -> list[str]:
    candidates = [text]

    # Prefer fenced JSON bodies when present.
    for block in text.split("```"):
        block = block.strip()
        if not block:
            continue
        if block.lower().startswith("json"):
            block = block[4:].strip()
        if block.startswith("{") or block.startswith("["):
            candidates.append(block)

    # Handle prose + JSON outputs by extracting the first balanced object
    # that appears to contain findings.
    marker = '"findings"'
    marker_pos = text.find(marker)
    if marker_pos != -1:
        open_brace = text.rfind("{", 0, marker_pos)
        if open_brace != -1:
            extracted = _extract_balanced_json_object(text, open_brace)
            if extracted:
                candidates.append(extracted)

    # Broad fallback: from first "{" to last "}".
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(text[first_brace:last_brace + 1].strip())

    # Preserve order but deduplicate.
    unique = []
    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)
    return unique


def _extract_balanced_json_object(text: str, start_index: int) -> str | None:
    depth = 0
    in_string = False
    i = start_index
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start_index:i + 1].strip()
        i += 1
    return None


def _extract_partial_findings(text: str) -> list[dict]:
    findings = []
    depth = 0
    start = None
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
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
                        obj = json.loads(text[start: i + 1])
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
    severity = _html.escape(finding.get("severity", "N/A"))
    category = _html.escape(finding.get("category", "N/A"))
    repo_escaped = _html.escape(repo)
    description = _html.escape(finding.get("description", "")).strip()
    remediation = finding.get("remediation", "")
    if not description:
        description = "No description provided."

    return (
        f"<body>"
        f"<ul>"
        f"<li><strong>Severity:</strong> {severity} | <strong>Category:</strong> {category}</li>"
        f"<li><strong>Repository:</strong> {repo_escaped}</li>"
        f"</ul>"
        f"<strong>Description</strong>"
        f"<pre>{description}</pre>"
        f"{f'<strong>Remediation</strong><pre>{_html.escape(remediation)}</pre>' if remediation else ''}"
        f"<em>Created by sweat security review agent</em>"
        f"</body>"
    )
