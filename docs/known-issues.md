# Known Issues

## Claude CLI exits with code 1 on Teams subscription

**Symptom**

```
Fatal error in message reader: Command failed with exit code 1 (exit code: 1)
Error output: Check stderr output for details
Exception: Command failed with exit code 1 (exit code: 1)
```

Or via sweat's error handling:

```
Error: Claude CLI exited with code 1 — you may need to re-authenticate.
Run `claude` interactively and log in, then retry.
```

**Cause**

The `claude_agent_sdk` runs the `claude` CLI as a subprocess. When the active Claude Code session is expired or tied to a different account (e.g. a personal subscription while the machine is enrolled in a Teams workspace), the CLI fails immediately with exit code 1 rather than returning a useful auth error.

**Fix**

Run Claude Code interactively and log in under the correct account using the `login` command:

```bash
claude login
```

Follow the login prompt. Once authenticated, re-run sweat — the SDK will pick up the new session automatically.

**Notes**

- This can happen after switching between a personal and a Teams subscription on the same machine.
- It can also occur if the CLI session simply expires after a long period of inactivity.
