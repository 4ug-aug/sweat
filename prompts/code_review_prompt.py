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
{{"findings": [{{"title": "Short descriptive title", "category": "inconsistent_pattern|dead_code|complexity", "priority": "Low|Medium|High", "estimated_minutes": 30, "pseudo_solution": "1. Do this\\n2. Then that", "description": "Detailed description referencing specific files/lines and the quality principle violated"}}]}}

Return exactly 3 findings, ranked by priority (highest first). If fewer than 3 issues exist, return as many as you find."""
