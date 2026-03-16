def build_review_response_prompt(
    pr_body: str,
    diff: str,
    review_body: str,
    inline_comments: list[dict],
) -> str:
    """Build prompt for addressing PR review feedback."""
    comments_text = ""
    if inline_comments:
        formatted = "\n".join(
            f"  {c.get('path', '')}:{c.get('line', '')} — {c.get('body', '')}"
            for c in inline_comments
        )
        comments_text = f"\n\n**Inline comments:**\n{formatted}"

    return f"""You are addressing code review feedback on a pull request.

## Original PR Description
{pr_body}

## Current Diff
```diff
{diff[:20000]}
```

## Review Feedback
{review_body}{comments_text}

## Your Task
Make targeted, minimal changes to address the reviewer's feedback. Be precise:
- Fix only what the reviewer asked about
- Don't refactor unrelated code
- Don't add new features unless explicitly requested
- If the reviewer asks a question, answer it in a comment or commit message rather than changing code unnecessarily

After making changes, the diff should clearly address each point raised in the review.
"""
