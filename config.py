import os

from dotenv import load_dotenv

load_dotenv()

ASANA_TOKEN = os.environ["ASANA_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ASANA_ASSIGNEE_GID = os.environ["ASANA_ASSIGNEE_GID"]

AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "audit.jsonl")

# Map Asana project GIDs to GitHub repos
PROJECTS = [
    {
        "asana_project_id": "1213637712779616",
        "github_repo": "4ug-aug/sweat",
        "branch_prefix": "agent/",
    }
]
