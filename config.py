import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

KNOWLEDGE_DIR = str(Path(__file__).resolve().parent / "knowledge")

ASANA_TOKEN = os.environ.get("ASANA_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_APP_ID = os.environ.get("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY_PATH = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "")
_key_from_env = os.environ.get("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n")
if GITHUB_APP_PRIVATE_KEY_PATH and not _key_from_env:
    try:
        GITHUB_APP_PRIVATE_KEY = Path(os.path.expanduser(GITHUB_APP_PRIVATE_KEY_PATH)).read_text()
    except OSError:
        GITHUB_APP_PRIVATE_KEY = ""
else:
    GITHUB_APP_PRIVATE_KEY = _key_from_env

AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "audit.jsonl")

RESPONSIBILITIES_STATE_PATH = os.environ.get("RESPONSIBILITIES_STATE_PATH", "responsibilities_state.json")


def _load_agents() -> list[dict]:
    """Load agents from sweat.config.json in CWD. Errors if not found."""
    cfg_path = Path.cwd() / "sweat.config.json"
    if cfg_path.is_file():
        with open(cfg_path) as f:
            data = json.load(f)
        return data["agents"] if isinstance(data, dict) else data
    return []


AGENTS = _load_agents()
