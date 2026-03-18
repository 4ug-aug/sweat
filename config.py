import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from agents.registry import AGENT_TYPES
from exceptions import ConfigError

load_dotenv()

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = str(Path(__file__).resolve().parent / "knowledge")

ASANA_TOKEN = os.environ.get("ASANA_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_APP_ID = os.environ.get("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY_PATH = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "")
_key_from_env = os.environ.get("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n")
if GITHUB_APP_PRIVATE_KEY_PATH and not _key_from_env:
    _key_path = Path(os.path.expanduser(GITHUB_APP_PRIVATE_KEY_PATH))
    if not _key_path.exists():
        raise ConfigError(
            f"GITHUB_APP_PRIVATE_KEY_PATH points to a file that does not exist: {_key_path}"
        )
    try:
        GITHUB_APP_PRIVATE_KEY = _key_path.read_text()
    except OSError as exc:
        raise ConfigError(
            f"Failed to read GitHub App private key from {_key_path}: {exc}"
        ) from exc
else:
    GITHUB_APP_PRIVATE_KEY = _key_from_env

AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "audit.jsonl")

RESPONSIBILITIES_STATE_PATH = os.environ.get(
    "RESPONSIBILITIES_STATE_PATH", "responsibilities_state.json"
)


_REQUIRED_AGENT_KEYS = {"id", "type"}


def _validate_agent_config(agent_cfg: dict, index: int) -> None:
    missing = _REQUIRED_AGENT_KEYS - agent_cfg.keys()
    if missing:
        raise ConfigError(
            f"Agent entry {index} in sweat.config.json is missing required keys: {missing}"
        )
    if agent_cfg["type"] not in AGENT_TYPES:
        logger.warning(
            "Agent entry %d has unknown type %r — it will be skipped at runtime",
            index,
            agent_cfg["type"],
        )


def _load_agents() -> list[dict]:
    """Load and validate agents from sweat.config.json in CWD."""
    cfg_path = Path.cwd() / "sweat.config.json"
    if not cfg_path.is_file():
        return []
    with open(cfg_path) as f:
        data = json.load(f)
    agents = data["agents"] if isinstance(data, dict) else data
    if not isinstance(agents, list):
        raise ConfigError(
            'sweat.config.json must contain a list of agents (or {"agents": [...]})'
        )
    for i, agent_cfg in enumerate(agents):
        _validate_agent_config(agent_cfg, i)
    return agents


AGENTS = _load_agents()
