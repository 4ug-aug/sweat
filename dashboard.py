import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

import config
from agent_state import read_all_states
from clients.github import GitHubClient

app = FastAPI(title="sweat dashboard")
DASHBOARD_HTML = Path(__file__).parent / "dashboard.html"


@app.get("/")
def index():
    return FileResponse(DASHBOARD_HTML, media_type="text/html")


@app.get("/api/agents")
def get_agents():
    states = read_all_states()
    result = []
    for agent_cfg in config.AGENTS:
        agent_id = agent_cfg["id"]
        state = states.get(agent_id, {})
        repos = [p["github_repo"] for p in agent_cfg.get("projects", [])]
        result.append({
            "id": agent_id,
            "type": agent_cfg["type"],
            "interval": agent_cfg.get("interval"),
            "repos": repos,
            "status": state.get("status", "unknown"),
            "loop_name": state.get("loop_name"),
            "last_run": state.get("last_run"),
            "last_error": state.get("last_error"),
        })
    return result


@app.get("/api/prs")
def get_prs():
    github = _build_github_client()
    if github is None:
        return JSONResponse({"error": "GitHub credentials not configured"}, status_code=500)

    repos = set()
    for agent_cfg in config.AGENTS:
        for project in agent_cfg.get("projects", []):
            if "github_repo" in project:
                repos.add(project["github_repo"])

    result = []
    for repo in sorted(repos):
        try:
            prs = github.get_open_prs(repo)
        except Exception:
            continue
        for pr in prs:
            try:
                pr["check_status"] = github.get_pr_check_status(repo, pr["number"])
            except Exception:
                pr["check_status"] = "unknown"
            try:
                pr["reviews"] = github.get_pr_reviews(repo, pr["number"])
            except Exception:
                pr["reviews"] = []
            pr["repo"] = repo
            result.append(pr)
    return result


@app.get("/api/log")
def get_log(last: int = 50):
    path = Path(config.AUDIT_LOG_PATH)
    if not path.exists():
        return []
    lines = path.read_text().strip().split("\n")
    entries = []
    for line in lines[-last:]:
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    entries.reverse()
    return entries


def _build_github_client() -> GitHubClient | None:
    if config.GITHUB_TOKEN:
        return GitHubClient(token=config.GITHUB_TOKEN)
    if config.GITHUB_APP_ID and config.GITHUB_APP_PRIVATE_KEY:
        return GitHubClient(app_id=config.GITHUB_APP_ID, private_key=config.GITHUB_APP_PRIVATE_KEY)
    return None
