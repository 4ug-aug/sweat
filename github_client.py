import base64
import tempfile

import git
from github import Github

import config

_SUMMARY_FILES = {"README.md", "README.rst", "README", "pyproject.toml", "package.json", "Makefile"}
_MAX_FILE_BYTES = 6_000
_MAX_TREE_ENTRIES = 120


def get_repo_summary(repo: str) -> str:
    """Return a concise text summary of the repo for use in Claude prompts.

    Includes the file tree (up to _MAX_TREE_ENTRIES paths) and the content of
    key files (README, pyproject.toml, package.json, etc.).
    """
    gh = Github(config.GITHUB_TOKEN)
    gh_repo = gh.get_repo(repo)

    # File tree
    tree = gh_repo.get_git_tree(gh_repo.default_branch, recursive=True).tree
    paths = [e.path for e in tree if e.type == "blob"][:_MAX_TREE_ENTRIES]
    tree_str = "\n".join(paths)

    # Key file contents
    snippets: list[str] = []
    for entry in tree:
        if entry.type != "blob":
            continue
        filename = entry.path.split("/")[-1]
        if filename in _SUMMARY_FILES:
            try:
                blob = gh_repo.get_git_blob(entry.sha)
                content = base64.b64decode(blob.content).decode("utf-8", errors="replace")
                content = content[:_MAX_FILE_BYTES]
                snippets.append(f"### {entry.path}\n{content}")
            except Exception:
                pass

    parts = [f"## File tree ({repo})\n{tree_str}"]
    if snippets:
        parts.append("## Key files\n" + "\n\n".join(snippets))
    return "\n\n".join(parts)


def clone_repo(repo: str) -> str:
    """Clone repo to a fresh temp dir, return the path.

    The cloned .git/config will contain GITHUB_TOKEN in the remote URL.
    Callers must delete the temp dir (e.g. shutil.rmtree) when done.
    """
    tmp = tempfile.mkdtemp(prefix="sweat_")
    url = f"https://x-access-token:{config.GITHUB_TOKEN}@github.com/{repo}.git"
    git.Repo.clone_from(url, tmp)
    return tmp


def create_branch(repo_path: str, branch_name: str) -> None:
    repo = git.Repo(repo_path)
    repo.git.checkout("-b", branch_name)


def commit_and_push(repo_path: str, branch_name: str, message: str) -> None:
    repo = git.Repo(repo_path)
    repo.git.add("--all")
    repo.index.commit(message)
    repo.git.push("--set-upstream", "origin", branch_name)


def create_pr(repo: str, branch: str, title: str, body: str) -> str:
    """Open a PR and return its URL."""
    gh = Github(config.GITHUB_TOKEN)
    gh_repo = gh.get_repo(repo)
    pr = gh_repo.create_pull(title=title, body=body, head=branch, base="main")
    return pr.html_url
