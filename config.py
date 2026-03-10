import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ASANA_TOKEN = os.environ["ASANA_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ASANA_ASSIGNEE_GID = os.environ["ASANA_ASSIGNEE_GID"]

# Map Asana project GIDs to GitHub repos
PROJECTS = [
    {
        "asana_project_id": "YOUR_PROJECT_GID",
        "github_repo": "augusttollerup/your-repo",
        "branch_prefix": "agent/",
    }
]
