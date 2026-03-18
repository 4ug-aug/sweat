from pathlib import Path

_SECURITY_STANDARD = (
    Path(__file__).parent.parent / "skills" / "security_reviewer" / "prompt.md"
).read_text()


def build_security_review_prompt(repo: str) -> str:
    return f"""You are a security engineer performing a vulnerability audit of the repository `{repo}`.

## Security Standard

{_SECURITY_STANDARD}

## Instructions

Scan the repository for security vulnerabilities. Use the audit checklists and patterns above as your guide.

For each finding provide:
- `title`: Short descriptive title (≤80 chars)
- `severity`: One of `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`
- `category`: One of `sql_injection`, `xss`, `auth_access_control`, `input_validation`, `secrets_exposure`, `header_security`
- `description`: Exact file path, line range, the vulnerable pattern, and its impact
- `remediation`: The corrected code or concrete steps to fix it
- `estimated_minutes`: Realistic developer fix time (integer)

Respond ONLY with valid JSON in this exact format — no markdown fences, no extra text:
{{"findings": [{{"title": "Short title", "severity": "HIGH", "category": "auth_access_control", "estimated_minutes": 30, "description": "Detailed description with file/line reference and impact", "remediation": "Corrected code or fix steps"}}]}}

Return up to 5 findings, ranked by severity (CRITICAL first). If fewer than 5 issues exist, return as many as you find. Omit INFO findings unless no higher-severity issues exist."""
