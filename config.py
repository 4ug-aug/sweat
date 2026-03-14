import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

KNOWLEDGE_DIR = str(Path(__file__).resolve().parent / "knowledge")

ASANA_TOKEN = os.environ["ASANA_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "audit.jsonl")

# Each entry defines an agent instance: its type, schedule, and project scope.
# Add more entries to run multiple agents targeting different repos/projects.
AGENTS = [
    {
        "id": "impl-intellagent",
        "type": "implementer",
        "replicas": 2,
        "interval": 3600,
        "asana_assignee_gid": os.environ["ASANA_ASSIGNEE_GID"],
        "projects": [
            {
                "asana_project_id": "1211944379207711",
                "github_repo": "SecureDevice-DevOps/IntellAgent",
                "branch_prefix": "agent/",
                "field_names": {
                    "priority": "Priority",
                    "estimated_time": "Estimated time",
                    "work_type": "Work Type",
                    "domain": "Domain",
                },
                "field_filters": {
                    "work_type": ["Bug / Defect", "Maintenance"],
                    "domain": ["Backend"],
                    "estimated_time": {"max": 240},  # ≤ 4 hours in minutes
                },
                "priority_order": ["High", "Medium", "Low"],
                "max_tasks_for_selector": 15,
            }
        ],
    },
    {
        "id": "reviewer-intellagent",
        "type": "reviewer",
        "interval": 60,
        "projects": [
            {
                "github_repo": "SecureDevice-DevOps/IntellAgent",
                "branch_prefix": "agent/",
            }
        ],
    },
    {
        "id": "code-reviewer-intellagent",
        "type": "code_reviewer",
        "interval": 86400,
        "projects": [
            {
                "asana_project_id": "1211944379207711",
                "github_repo": "SecureDevice-DevOps/IntellAgent",
                "quality_doc_path": "docs/code-quality.md",
            }
        ],
    },
]
