from prompts import knowledge_blocks


def build_review_prompt(meta: dict, diff: str, repo_summary: str, knowledge_dir: str = "") -> str:
    kb_before, kb_after = knowledge_blocks(knowledge_dir)
    knowledge_before = f"\n## Knowledge base\n{kb_before}\n" if kb_before else ""
    knowledge_after = f"\n{kb_after}" if kb_after else ""

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
