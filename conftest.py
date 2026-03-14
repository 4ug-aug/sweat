import os
import tempfile

# Set dummy env vars so config.py doesn't raise during test collection
os.environ.setdefault("ASANA_TOKEN", "test-token")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("ASANA_ASSIGNEE_GID", "test-gid")

# Redirect audit log to a temp file so tests don't pollute the production log
os.environ.setdefault("AUDIT_LOG_PATH", os.path.join(tempfile.gettempdir(), "test_audit.jsonl"))
