import base64
import tempfile

import git
from github import Auth, Github

from exceptions import GitHubError

_PRIORITY_FILES = {"CLAUDE.md"}
_SUMMARY_FILES = {"README.md", "README.rst", "README", "package.json"}
_ALL_CONTEXT_FILES = _PRIORITY_FILES | _SUMMARY_FILES
_MAX_FILE_BYTES = 6_000
_MAX_TREE_ENTRIES = 120


class GitHubClient:
    def __init__(self, token: str):
        self._token = token
        self._gh = Github(auth=Auth.Token(token))

    def get_repo_summary(self, repo: str) -> str:
        """Return a concise text summary of the repo for use in Claude prompts."""
        gh_repo = self._gh.get_repo(repo)

        tree = gh_repo.get_git_tree(gh_repo.default_branch, recursive=True).tree
        paths = [e.path for e in tree if e.type == "blob"][:_MAX_TREE_ENTRIES]
        tree_str = "\n".join(paths)

        priority: list[str] = []
        supporting: list[str] = []
        for entry in tree:
            if entry.type != "blob":
                continue
            filename = entry.path.split("/")[-1]
            if filename not in _ALL_CONTEXT_FILES:
                continue
            try:
                blob = gh_repo.get_git_blob(entry.sha)
                content = base64.b64decode(blob.content).decode("utf-8", errors="replace")
                content = content[:_MAX_FILE_BYTES]
                snippet = f"### {entry.path}\n{content}"
                if filename in _PRIORITY_FILES:
                    priority.append(snippet)
                else:
                    supporting.append(snippet)
            except Exception:
                pass

        snippets = priority + supporting
        parts = [f"## File tree ({repo})\n{tree_str}"]
        if snippets:
            parts.append("## Key files\n" + "\n\n".join(snippets))
        return "\n\n".join(parts)

    def clone_repo(self, repo: str) -> str:
        """Clone repo to a fresh temp dir, return the path."""
        try:
            tmp = tempfile.mkdtemp(prefix="sweat_")
            url = f"https://x-access-token:{self._token}@github.com/{repo}.git"
            git.Repo.clone_from(url, tmp)
            return tmp
        except Exception as exc:
            raise GitHubError(f"Failed to clone {repo}: {exc}") from exc

    def create_branch(self, repo_path: str, branch_name: str) -> None:
        try:
            repo = git.Repo(repo_path)
            repo.git.checkout("-b", branch_name)
        except Exception as exc:
            raise GitHubError(f"Failed to create branch {branch_name}: {exc}") from exc

    def commit_and_push(self, repo_path: str, branch_name: str, message: str) -> None:
        try:
            repo = git.Repo(repo_path)
            repo.git.add("--all")
            repo.index.commit(message)
            repo.git.push("--set-upstream", "origin", branch_name)
        except Exception as exc:
            raise GitHubError(
                f"Failed to commit and push branch {branch_name}: {exc}"
            ) from exc

    def create_pr(self, repo: str, branch: str, title: str, body: str) -> str:
        """Open a PR and return its URL."""
        try:
            gh_repo = self._gh.get_repo(repo)
            pr = gh_repo.create_pull(title=title, body=body, head=branch, base="main")
            return pr.html_url
        except Exception as exc:
            raise GitHubError(f"Failed to create PR for {repo}/{branch}: {exc}") from exc

    def get_bot_login(self) -> str:
        return self._gh.get_user().login

    def get_open_prs(self, repo: str) -> list[dict]:
        prs = self._gh.get_repo(repo).get_pulls(state="open", sort="created")
        return [
            {
                "number": pr.number,
                "title": pr.title,
                "author_login": pr.user.login,
                "head_branch": pr.head.ref,
                "base_branch": pr.base.ref,
                "html_url": pr.html_url,
            }
            for pr in prs
            if not pr.draft
        ]

    def has_bot_reviewed(self, repo: str, pr_number: int, bot_login: str) -> bool:
        reviews = self._gh.get_repo(repo).get_pull(pr_number).get_reviews()
        return any(r.user.login == bot_login for r in reviews)

    def get_pr_metadata(self, repo: str, pr_number: int) -> dict:
        pr = self._gh.get_repo(repo).get_pull(pr_number)
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body or "",
            "author_login": pr.user.login,
            "head_branch": pr.head.ref,
            "base_branch": pr.base.ref,
            "html_url": pr.html_url,
        }

    def get_pr_diff(self, repo: str, pr_number: int) -> str:
        files = self._gh.get_repo(repo).get_pull(pr_number).get_files()
        parts = [f"--- {f.filename}\n{f.patch or ''}" for f in files if f.patch]
        return "\n\n".join(parts)

    def post_pr_review(
        self, repo: str, pr_number: int, body: str, event: str = "COMMENT"
    ) -> None:
        self._gh.get_repo(repo).get_pull(pr_number).create_review(body=body, event=event)
