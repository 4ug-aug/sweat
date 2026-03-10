import tempfile
import git
from github import Github
import config


def clone_repo(repo: str) -> str:
    """Clone repo to a fresh temp dir, return the path."""
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
