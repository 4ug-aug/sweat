import os

# Set dummy env vars so config.py doesn't raise during test collection
os.environ.setdefault("ASANA_TOKEN", "test-token")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("ASANA_ASSIGNEE_GID", "test-gid")
