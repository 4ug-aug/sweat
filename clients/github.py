import asyncio
import base64
import logging
import tempfile
from datetime import datetime, timedelta, timezone

import git
from github import Auth, Github, GithubIntegration

from exceptions import GitHubError

logger = logging.getLogger(__name__)

_PRIORITY_FILES = {"CLAUDE.md"}
_SUMMARY_FILES = {"README.md", "README.rst", "README", "package.json"}
_ALL_CONTEXT_FILES = _PRIORITY_FILES | _SUMMARY_FILES
_MAX_FILE_BYTES = 6_000
_MAX_TREE_ENTRIES = 120


class GitHubClient:
    def __init__(self, token: str = "", app_id: str = "", private_key: str = ""):
        if app_id and private_key:
            self._mode = "app"
            self._app_auth = Auth.AppAuth(int(app_id), private_key)
            self._integration = GithubIntegration(int(app_id), private_key)
            self._install_cache: dict[str, tuple[str, datetime]] = {}
            self._gh = Github(auth=self._app_auth)
        else:
            self._mode = "pat"
            self._token = token
            self._gh = Github(auth=Auth.Token(token))

    def _token_for_owner(self, owner: str) -> str:
        """Returns a valid installation access token for the given org/owner, with caching."""
        cached = self._install_cache.get(owner)
        if cached:
            token, expires_at = cached
            if datetime.now(timezone.utc) < expires_at - timedelta(minutes=5):
                return token
        for inst in self._integration.get_installations():
            if inst.account.login == owner:
                access = self._integration.get_access_token(inst.id)
                self._install_cache[owner] = (access.token, access.expires_at)
                return access.token
        raise ValueError(f"No GitHub App installation found for owner: {owner}")

    def _get_gh(self, repo: str | None = None) -> Github:
        """Returns authenticated Github instance. App mode resolves installation token per repo."""
        if self._mode == "pat":
            return self._gh
        if repo is None:
            return self._gh
        return Github(auth=Auth.Token(self._token_for_owner(repo.split("/")[0])))

    def get_repo_summary(self, repo: str) -> str:
        """Return a concise text summary of the repo for use in Claude prompts."""
        gh_repo = self._get_gh(repo).get_repo(repo)

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
            except Exception as exc:
                logger.warning("Failed to decode blob for %s: %s", entry.path, exc)

        snippets = priority + supporting
        parts = [f"## File tree ({repo})\n{tree_str}"]
        if snippets:
            parts.append("## Key files\n" + "\n\n".join(snippets))
        return "\n\n".join(parts)

    def clone_repo(self, repo: str) -> str:
        """Clone repo to a fresh temp dir, return the path."""
        try:
            tmp = tempfile.mkdtemp(prefix="sweat_")
            if self._mode == "app":
                token = self._token_for_owner(repo.split("/")[0])
            else:
                token = self._token
            url = f"https://x-access-token:{token}@github.com/{repo}.git"
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
            gh_repo = self._get_gh(repo).get_repo(repo)
            pr = gh_repo.create_pull(title=title, body=body, head=branch, base="main")
            return pr.html_url
        except Exception as exc:
            raise GitHubError(f"Failed to create PR for {repo}/{branch}: {exc}") from exc

    def get_bot_login(self) -> str:
        if self._mode == "app":
            return self._gh.get_app().slug + "[bot]"
        return self._gh.get_user().login

    def get_open_prs(self, repo: str) -> list[dict]:
        prs = self._get_gh(repo).get_repo(repo).get_pulls(state="open", sort="created")
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
        reviews = self._get_gh(repo).get_repo(repo).get_pull(pr_number).get_reviews()
        return any(r.user.login == bot_login for r in reviews)

    def get_pr_metadata(self, repo: str, pr_number: int) -> dict:
        pr = self._get_gh(repo).get_repo(repo).get_pull(pr_number)
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
        files = self._get_gh(repo).get_repo(repo).get_pull(pr_number).get_files()
        parts = [f"--- {f.filename}\n{f.patch or ''}" for f in files if f.patch]
        return "\n\n".join(parts)

    def post_pr_review(
        self, repo: str, pr_number: int, body: str, event: str = "COMMENT"
    ) -> None:
        self._get_gh(repo).get_repo(repo).get_pull(pr_number).create_review(body=body, event=event)

    def get_pr_reviews(self, repo: str, pr_number: int) -> list[dict]:
        try:
            reviews = self._get_gh(repo).get_repo(repo).get_pull(pr_number).get_reviews()
            return [
                {
                    "id": r.id,
                    "user_login": r.user.login,
                    "state": r.state,
                    "body": r.body or "",
                    "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                }
                for r in reviews
            ]
        except Exception as exc:
            raise GitHubError(f"Failed to get reviews for {repo}#{pr_number}: {exc}") from exc

    def get_review_comments(self, repo: str, pr_number: int, review_id: int) -> list[dict]:
        try:
            review = self._get_gh(repo).get_repo(repo).get_pull(pr_number).get_review(review_id)
            comments = review.get_comments()
            return [
                {
                    "path": c.path,
                    "line": c.original_line,
                    "body": c.body,
                }
                for c in comments
            ]
        except Exception as exc:
            raise GitHubError(f"Failed to get review comments for {repo}#{pr_number} review {review_id}: {exc}") from exc

    def checkout_branch(self, repo_path: str, branch: str) -> None:
        try:
            repo = git.Repo(repo_path)
            repo.git.fetch("origin")
            repo.git.checkout(branch)
        except Exception as exc:
            raise GitHubError(f"Failed to checkout branch {branch}: {exc}") from exc

    def post_pr_comment(self, repo: str, pr_number: int, body: str) -> None:
        try:
            self._get_gh(repo).get_repo(repo).get_issue(pr_number).create_comment(body)
        except Exception as exc:
            raise GitHubError(f"Failed to post comment on {repo}#{pr_number}: {exc}") from exc

    def get_pr_check_status(self, repo: str, pr_number: int) -> str:
        try:
            gh = self._get_gh(repo)
            pr = gh.get_repo(repo).get_pull(pr_number)
            sha = pr.head.sha
            status = gh.get_repo(repo).get_commit(sha).get_combined_status()
            return status.state  # "success", "failure", "pending", "error"
        except Exception as exc:
            raise GitHubError(f"Failed to get check status for {repo}#{pr_number}: {exc}") from exc

    def get_failed_check_details(self, repo: str, pr_number: int) -> list[dict]:
        try:
            gh = self._get_gh(repo)
            pr = gh.get_repo(repo).get_pull(pr_number)
            sha = pr.head.sha
            check_runs = gh.get_repo(repo).get_commit(sha).get_check_runs()
            return [
                {
                    "name": run.name,
                    "output": (run.output.text or "")[:3000] if run.output else "",
                }
                for run in check_runs
                if run.conclusion == "failure"
            ]
        except Exception as exc:
            raise GitHubError(f"Failed to get failed checks for {repo}#{pr_number}: {exc}") from exc

    def get_pr_issue_comments(self, repo: str, pr_number: int) -> list[dict]:
        try:
            comments = self._get_gh(repo).get_repo(repo).get_issue(pr_number).get_comments()
            return [
                {
                    "id": c.id,
                    "user_login": c.user.login,
                    "body": c.body,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in comments
            ]
        except Exception as exc:
            raise GitHubError(f"Failed to get issue comments for {repo}#{pr_number}: {exc}") from exc

    def get_pr_comment_threads(self, repo: str, pr_number: int) -> list[dict]:
        try:
            comments = list(self._get_gh(repo).get_repo(repo).get_pull(pr_number).get_review_comments())
            # Group by in_reply_to_id
            roots = [c for c in comments if not getattr(c, "in_reply_to_id", None)]
            replies_by_root: dict[int, list] = {}
            for c in comments:
                parent_id = getattr(c, "in_reply_to_id", None)
                if parent_id is not None:
                    replies_by_root.setdefault(parent_id, []).append(c)

            def _comment_dict(c) -> dict:
                return {
                    "id": c.id,
                    "user_login": c.user.login,
                    "body": c.body,
                    "path": c.path,
                    "line": getattr(c, "original_line", None),
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }

            return [
                {
                    "root": _comment_dict(root),
                    "replies": [_comment_dict(r) for r in replies_by_root.get(root.id, [])],
                }
                for root in roots
            ]
        except Exception as exc:
            raise GitHubError(f"Failed to get comment threads for {repo}#{pr_number}: {exc}") from exc

    def reply_to_pr_comment(self, repo: str, pr_number: int, comment_id: int, body: str) -> None:
        try:
            self._get_gh(repo).get_repo(repo).get_pull(pr_number).create_review_comment_reply(comment_id, body)
        except Exception as exc:
            raise GitHubError(f"Failed to reply to comment {comment_id} on {repo}#{pr_number}: {exc}") from exc

    def get_latest_review_timestamp(self, repo: str, pr_number: int, bot_login: str) -> str | None:
        try:
            reviews = self._get_gh(repo).get_repo(repo).get_pull(pr_number).get_reviews()
            bot_reviews = [r for r in reviews if r.user.login == bot_login and r.submitted_at]
            if not bot_reviews:
                return None
            latest = max(bot_reviews, key=lambda r: r.submitted_at)
            return latest.submitted_at.isoformat()
        except Exception as exc:
            raise GitHubError(f"Failed to get latest review timestamp for {repo}#{pr_number}: {exc}") from exc

    def get_latest_commit_timestamp(self, repo: str, pr_number: int) -> str:
        try:
            pr = self._get_gh(repo).get_repo(repo).get_pull(pr_number)
            sha = pr.head.sha
            commit = pr.head.repo.get_commit(sha)
            return commit.commit.author.date.isoformat()
        except Exception as exc:
            raise GitHubError(f"Failed to get latest commit timestamp for {repo}#{pr_number}: {exc}") from exc

    # Async wrappers — delegate to sync methods via to_thread to unblock the event loop.

    async def get_repo_summary_async(self, repo: str) -> str:
        return await asyncio.to_thread(self.get_repo_summary, repo)

    async def clone_repo_async(self, repo: str) -> str:
        return await asyncio.to_thread(self.clone_repo, repo)

    async def create_branch_async(self, repo_path: str, branch_name: str) -> None:
        await asyncio.to_thread(self.create_branch, repo_path, branch_name)

    async def commit_and_push_async(self, repo_path: str, branch_name: str, message: str) -> None:
        await asyncio.to_thread(self.commit_and_push, repo_path, branch_name, message)

    async def create_pr_async(self, repo: str, branch: str, title: str, body: str) -> str:
        return await asyncio.to_thread(self.create_pr, repo, branch, title, body)

    async def get_bot_login_async(self) -> str:
        return await asyncio.to_thread(self.get_bot_login)

    async def get_open_prs_async(self, repo: str) -> list[dict]:
        return await asyncio.to_thread(self.get_open_prs, repo)

    async def has_bot_reviewed_async(self, repo: str, pr_number: int, bot_login: str) -> bool:
        return await asyncio.to_thread(self.has_bot_reviewed, repo, pr_number, bot_login)

    async def get_pr_metadata_async(self, repo: str, pr_number: int) -> dict:
        return await asyncio.to_thread(self.get_pr_metadata, repo, pr_number)

    async def get_pr_diff_async(self, repo: str, pr_number: int) -> str:
        return await asyncio.to_thread(self.get_pr_diff, repo, pr_number)

    async def post_pr_review_async(
        self, repo: str, pr_number: int, body: str, event: str = "COMMENT"
    ) -> None:
        await asyncio.to_thread(self.post_pr_review, repo, pr_number, body, event)

    async def get_pr_reviews_async(self, repo: str, pr_number: int) -> list[dict]:
        return await asyncio.to_thread(self.get_pr_reviews, repo, pr_number)

    async def get_review_comments_async(self, repo: str, pr_number: int, review_id: int) -> list[dict]:
        return await asyncio.to_thread(self.get_review_comments, repo, pr_number, review_id)

    async def checkout_branch_async(self, repo_path: str, branch: str) -> None:
        await asyncio.to_thread(self.checkout_branch, repo_path, branch)

    async def post_pr_comment_async(self, repo: str, pr_number: int, body: str) -> None:
        await asyncio.to_thread(self.post_pr_comment, repo, pr_number, body)

    async def get_pr_check_status_async(self, repo: str, pr_number: int) -> str:
        return await asyncio.to_thread(self.get_pr_check_status, repo, pr_number)

    async def get_failed_check_details_async(self, repo: str, pr_number: int) -> list[dict]:
        return await asyncio.to_thread(self.get_failed_check_details, repo, pr_number)

    async def get_pr_issue_comments_async(self, repo: str, pr_number: int) -> list[dict]:
        return await asyncio.to_thread(self.get_pr_issue_comments, repo, pr_number)

    async def get_pr_comment_threads_async(self, repo: str, pr_number: int) -> list[dict]:
        return await asyncio.to_thread(self.get_pr_comment_threads, repo, pr_number)

    async def reply_to_pr_comment_async(self, repo: str, pr_number: int, comment_id: int, body: str) -> None:
        await asyncio.to_thread(self.reply_to_pr_comment, repo, pr_number, comment_id, body)

    async def get_latest_review_timestamp_async(self, repo: str, pr_number: int, bot_login: str) -> str | None:
        return await asyncio.to_thread(self.get_latest_review_timestamp, repo, pr_number, bot_login)

    async def get_latest_commit_timestamp_async(self, repo: str, pr_number: int) -> str:
        return await asyncio.to_thread(self.get_latest_commit_timestamp, repo, pr_number)
