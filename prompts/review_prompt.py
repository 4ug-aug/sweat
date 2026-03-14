def build_review_prompt(meta: dict, diff: str, repo_summary: str, knowledge_dir: str = "") -> str:
    knowledge_before = ""
    knowledge_after = ""
    if knowledge_dir:
        knowledge_before = f"""
## Knowledge base

Before reviewing, read `{knowledge_dir}/MEMORY.md` to see available knowledge topics. Then read any files relevant to this review (e.g. pitfalls, patterns). Do not read all files — only what's relevant based on the index.

"""
        knowledge_after = f"""

After completing your review, write a structured entry to the most relevant knowledge file(s) in `{knowledge_dir}/`. Use the entry format shown in MEMORY.md. If you found a pitfall, write to `pitfalls/`. If you observed a positive pattern, write to `patterns/`. Keep entries concise and factual. Only update MEMORY.md if you created a new topic file.
"""

    return f"""You are an expert code reviewer. Review the following pull request and provide structured feedback.
{knowledge_before}

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
{knowledge_after}"""
