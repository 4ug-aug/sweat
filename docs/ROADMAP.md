# SWEAT Roadmap — Digital Twin Ideas

The goal is for SWEAT to behave like August would if August had infinite time. Below are ideas grouped by the kind of work the twin could take on.

---

## 1. Task Organisation

**Triage inbox tasks**
On each run, scan tasks in a designated "Inbox/Backlog" project and sort them into the right projects, sections, and priorities. Claude reads the task name/description and decides where it belongs — the same judgment call you make when clearing your inbox.

**Break down large tasks into subtasks**
Detect tasks that are too big to execute in one go (vague scope, no clear definition of done) and automatically decompose them into concrete subtasks. Claude writes the subtasks, attaches them, and adds a comment explaining the breakdown.

**Detect and flag duplicates**
Before creating or picking up a task, scan for existing tasks with similar names or descriptions and flag potential duplicates with a comment linking the related items.

**Section hygiene**
Identify tasks sitting in the wrong section (e.g. tasks marked "Done" but still in "In Progress", or tasks with no section) and move them to the right place.

---

## 2. Task Description Improvement

**Enrich vague tasks**
When a task has a title but minimal description, Claude searches the relevant codebase and writes a proper description: what the problem is, where in the code it lives, what a good solution would look like, and what done looks like. This is one of the most valuable things a twin could do — tasks go from "fix the login thing" to an actionable spec.

**Add acceptance criteria**
For any task missing acceptance criteria, generate a checklist of conditions that would make the task "done". Attach it as a comment or edit the description.

**Add reproduction steps for bugs**
For bug reports, Claude reads the description, looks at the relevant code, and writes clear reproduction steps and expected vs. actual behaviour — the kind of thing that turns a frustrating bug into something another developer can actually fix.

**Link related tasks and PRs**
Scan a task's description against recent PRs and other tasks, and add links to related work. Keeps context connected without manual effort.

---

## 3. Time Estimation

**Estimate task effort**
After reading a task and the relevant code, post a comment with a rough time estimate and confidence level. Could use a simple taxonomy: S/M/L/XL, or hours. Over time, calibrate estimates against how long tasks actually took.

**Flag under-estimated milestones**
Look at a milestone or sprint's total estimated work vs. the time available, and flag when a sprint is over-committed before it starts.

**Identify blockers**
Read task descriptions and subtasks and flag when a task is likely blocked by another unfinished task — before it becomes a surprise.

---

## 4. Delegation

**Assign tasks to the right person**
Given a team member roster (names + areas of ownership), read a task and assign it to the most appropriate person. Could use a simple config mapping skills/areas to Asana user GIDs.

**Draft a handoff comment**
When delegating, don't just assign — write a comment that gives the assignee everything they need: context, the relevant code location, what done looks like, and any gotchas Claude found.

**Identify tasks that don't need a human**
Flag tasks that SWEAT itself could handle: small bugs, documentation updates, test additions, config changes. Assign them to SWEAT and let it run.

---

## 5. Implementation (Current + Extensions)

**Handle more task types**
Currently SWEAT targets code fixes. Extend to:
- *Documentation tasks* — update READMEs, add docstrings, write changelogs
- *Test coverage tasks* — identify untested code paths and write tests
- *Refactoring tasks* — rename, extract, simplify with a clear spec
- *Dependency upgrades* — bump a package, fix breaking changes, update tests

**Self-assess before opening a PR**
After implementing, run the test suite and linter, and only open a PR if they pass. Post a summary of what was run and what passed/failed in the PR body.

**Iterative PR feedback**
Watch for review comments on open PRs created by SWEAT, read them, and push follow-up commits addressing the feedback — closing the loop without human intervention.

**Parallel task execution**
Run multiple tasks concurrently across different repos — one agent per task, each in an isolated worktree. Currently SWEAT does one task per cron run.

---

## 6. Memory and Learning

**Task outcome tracking**
After a PR is merged or closed, record the outcome against the original task. Over time, build a picture of which kinds of tasks SWEAT handles well vs. poorly, and use that to calibrate the feasibility scorer.

**Codebase familiarity**
Maintain a persistent notes file per repo that summarises key architecture decisions, common patterns, where tests live, how to run them. Prepend this to the agent prompt so Claude hits the ground running rather than re-exploring from scratch every time.

**Style preferences**
Record preferences learned from PR review feedback — naming conventions, preferred patterns, things the reviewer always flags. Include these in future prompts for the same repo.

---

## 7. Reporting

**Daily digest**
At the end of each day, post a summary to Slack or email: tasks picked up, PRs opened, tasks enriched, tasks delegated, things that failed. The same update August would give in a standup.

**Weekly planning assist**
On Monday morning, look at the week's tasks and draft a prioritised plan: what SWEAT will handle autonomously, what needs August, what's blocked.

---

## Principles for Extending

- **Transparency over autonomy**: always comment on what was done and why, so everything is auditable
- **Propose before acting on destructive changes**: reassigning tasks, closing tasks, or editing descriptions should be commented first and actioned on the next run if not rejected
- **Stay scoped**: one task per run per project — parallelism can come later once reliability is established
- **Match August's judgment, not just his actions**: the goal isn't automation, it's a twin that makes the same calls August would
