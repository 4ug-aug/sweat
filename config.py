import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

KNOWLEDGE_DIR = str(Path(__file__).resolve().parent / "knowledge")

ASANA_TOKEN = os.environ.get("ASANA_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "audit.jsonl")


def _load_agents() -> list[dict]:
    """Load agents from sweat.config.json in CWD. Errors if not found."""
    cfg_path = Path.cwd() / "sweat.config.json"
    if cfg_path.is_file():
        with open(cfg_path) as f:
            data = json.load(f)
        return data["agents"] if isinstance(data, dict) else data
    return []


AGENTS = _load_agents()
