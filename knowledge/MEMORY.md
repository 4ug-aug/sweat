# Knowledge Base Index

This file indexes all knowledge topics available to agents. Read only the files relevant to your current task.

## Entry format

Each topic file contains entries in this format:

```
## [YYYY-MM] Short title
**Context**: What was being done
**Outcome**: What happened
**Learning**: The takeaway
**Applies to**: tag1, tag2
```

## Topic files

| File | Purpose | When to read |
|------|---------|--------------|
| `patterns/general.md` | Reusable patterns that work well across the codebase | Starting any implementation task |
| `patterns/testing.md` | Testing patterns and conventions | Writing or updating tests |
| `patterns/architecture.md` | Architectural decisions and conventions | Making structural changes or adding new modules |
| `pitfalls/rejected_prs.md` | Lessons from PRs that were rejected or needed rework | Before opening a PR |
| `pitfalls/common_mistakes.md` | Frequently made mistakes to avoid | During implementation |
| `tasks/by_type.md` | Notes on how different task types should be approached | When selecting or starting a task |
