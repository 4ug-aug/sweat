def build_comment_response_prompt(
    comment_threads: list[dict],
    diff: str,
    repo_summary: str,
) -> str:
    """Build prompt for responding to PR comments."""
    threads_text = ""
    for thread in comment_threads:
        root = thread.get("root", {})
        replies = thread.get("replies", [])
        threads_text += f"\n**@{root.get('user_login', '')}** on `{root.get('path', '')}:{root.get('line', '')}`:\n"
        threads_text += f"> {root.get('body', '')}\n"
        for reply in replies:
            threads_text += f"\n  **@{reply.get('user_login', '')}**: {reply.get('body', '')}\n"

    return f"""You are responding to comments on a pull request.

## Repository Context
{repo_summary[:3000]}

## PR Diff
```diff
{diff[:15000]}
```

## Comment Threads
{threads_text}

## Your Task
For each comment thread, either:
1. **Implement the suggestion**: Make the code changes the commenter is asking for
2. **Answer the question**: If the commenter is asking a question rather than requesting a change, output a text reply

If you are providing a text reply (not making code changes), output it as:
REPLY: <your reply text>

If you are making code changes, make them directly. After the changes, the comments should be considered addressed.

Be respectful and constructive in any replies.
"""
