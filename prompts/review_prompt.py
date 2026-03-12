def build_review_prompt(meta: dict, diff: str, repo_summary: str) -> str:
    return f"""You are an expert code reviewer. Review the following pull request and provide structured feedback.

## Repository context

{repo_summary}

## Pull request

**Title:** {meta['title']}
**Author:** {meta['author_login']}
**Branch:** {meta['head_branch']} → {meta['base_branch']}
**URL:** {meta['html_url']}

**Description:**
{meta['body'] or 'No description provided.'}

## Diff

```diff
{diff}
```

## Instructions

Produce a structured review with exactly these four sections:

### Summary
What does this PR do? (2-4 sentences)

### Concerns
List any bugs, security issues, logic errors, or correctness problems. Reference specific files and line numbers from the diff where applicable. If none, write "None."

### Suggestions
Non-blocking improvements: style, naming, performance, test coverage, documentation. If none, write "None."

### Verdict
One of:
- `LGTM` — no concerns, ready to merge
- `LGTM with minor suggestions` — suggestions only, no blocking concerns
- `Changes requested` — has concerns that should be addressed before merging

Be direct and concise. Focus on correctness and clarity, not style preferences.
"""
