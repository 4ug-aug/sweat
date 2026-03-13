# End-to-End Testing

## Prerequisites

1. Copy `.env.example` to `.env` and fill in all values
2. Set up `config.py` with a real Asana project GID and GitHub repo
3. Create a dummy Asana task in the project: "Add a TODO comment in README"
4. Ensure the GitHub repo has a `main` branch and you have push access

## Running the dry-run

```bash
uv run python main.py --dry-run
```

Expected output:
```
Selected task: [<gid>] Add a TODO comment in README
[dry-run] Would assign, clone, implement, and open PR. Exiting.
```

## Running the full E2E

```bash
uv run python main.py
```

Verify:
- [ ] Task in Asana is assigned to you
- [ ] A comment appears on the Asana task with the proposed approach
- [ ] A branch `agent/asana-<gid>-...` appears on GitHub
- [ ] A PR is opened with the Asana task URL in the body
- [ ] A second Asana comment appears with the PR link

## Scheduling with cron

Add to crontab (`crontab -e`):

```
0 * * * * cd /path/to/sweat && uv run python main.py >> /tmp/sweat.log 2>&1
```

This runs every hour. Check `/tmp/sweat.log` for output.
