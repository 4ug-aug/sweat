import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

KNOWLEDGE_DIR = str(Path(__file__).resolve().parent / "knowledge")

ASANA_TOKEN = os.environ.get("ASANA_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "audit.jsonl")


_DEFAULT_AGENTS = [
    {
        "id": "impl-intellagent",
        "type": "implementer",
        "replicas": 2,
        "interval": 3600,
        "asana_assignee_gid": os.environ.get("ASANA_ASSIGNEE_GID", ""),
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
                    "estimated_time": {"max": 240},
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


def _load_agents() -> list[dict]:
    """Load agents from sweat.config.json, falling back to hardcoded defaults."""
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        cfg_path = base / "sweat.config.json"
        if cfg_path.is_file():
            with open(cfg_path) as f:
                data = json.load(f)
            return data.get("agents", data) if isinstance(data, dict) else data
    return _DEFAULT_AGENTS


AGENTS = _load_agents()
