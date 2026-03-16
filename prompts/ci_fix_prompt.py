def build_ci_fix_prompt(
    diff: str,
    failed_checks: list[dict],
    repo_summary: str,
) -> str:
    """Build prompt for fixing CI failures."""
    checks_text = ""
    for check in failed_checks:
        output = check.get("output", "")[:3000]
        checks_text += f"\n### {check.get('name', 'Unknown check')}\n```\n{output}\n```\n"

    return f"""You are fixing CI failures on a pull request.

## Repository Context
{repo_summary[:3000]}

## PR Diff
```diff
{diff[:15000]}
```

## Failed Checks
{checks_text}

## Your Task
Diagnose why the CI checks are failing and fix the root cause. Be focused:
- Fix the specific failures shown above
- Don't modify unrelated code
- Run tests locally if possible to verify fixes
- If a test is wrong (not the code), fix the test

Make the minimal changes needed to make the checks pass.
"""
