import base64
import os
from unittest.mock import MagicMock, patch

import pytest

from clients.github import GitHubClient


@patch("clients.github.tempfile.mkdtemp")
@patch("clients.github.git.Repo.clone_from")
@patch("clients.github.Github")
def test_clone_repo_returns_path(mock_github_class, mock_clone, mock_mkdtemp):
    mock_clone.return_value = MagicMock()
    mock_mkdtemp.return_value = "/tmp/sweat_test123"
    client = GitHubClient("test-token")

    path = client.clone_repo("augusttollerup/myrepo")

    assert os.path.isabs(path)
    assert mock_clone.called
    url = mock_clone.call_args[0][0]
    assert "augusttollerup/myrepo" in url


@patch("clients.github.git.Repo")
@patch("clients.github.Github")
def test_create_branch(mock_github_class, mock_repo_class):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    client = GitHubClient("test-token")

    client.create_branch("/tmp/somerepo", "agent/asana-111-fix-login")

    mock_repo.git.checkout.assert_called_once_with("-b", "agent/asana-111-fix-login")


@patch("clients.github.git.Repo")
@patch("clients.github.Github")
def test_commit_and_push(mock_github_class, mock_repo_class):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    client = GitHubClient("test-token")

    client.commit_and_push("/tmp/somerepo", "agent/asana-111-fix-login", "fix: resolve login bug")

    mock_repo.git.add.assert_called_once_with("--all")
    mock_repo.index.commit.assert_called_once_with("fix: resolve login bug")
    mock_repo.git.push.assert_called_once_with("--set-upstream", "origin", "agent/asana-111-fix-login")


@patch("clients.github.Github")
def test_create_pr_returns_url(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    mock_pr = MagicMock()
    mock_pr.html_url = "https://github.com/augusttollerup/myrepo/pull/42"
    mock_repo.create_pull.return_value = mock_pr
    client = GitHubClient("test-token")

    url = client.create_pr(
        repo="augusttollerup/myrepo",
        branch="agent/asana-111-fix-login",
        title="fix: resolve login bug",
        body="Fixes Asana task #111",
    )

    assert url == "https://github.com/augusttollerup/myrepo/pull/42"
    mock_repo.create_pull.assert_called_once_with(
        title="fix: resolve login bug",
        body="Fixes Asana task #111",
        head="agent/asana-111-fix-login",
        base="main",
    )


@patch("clients.github.Github")
def test_get_repo_summary_includes_tree_and_readme(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    mock_repo.default_branch = "main"

    def make_entry(path, sha):
        e = MagicMock()
        e.type = "blob"
        e.path = path
        e.sha = sha
        return e

    mock_repo.get_git_tree.return_value.tree = [
        make_entry("CLAUDE.md", "sha1"),
        make_entry("README.md", "sha2"),
    ]

    def fake_blob(sha):
        b = MagicMock()
        if sha == "sha1":
            b.content = base64.b64encode(b"# Project instructions").decode()
        else:
            b.content = base64.b64encode(b"# My Project\nDoes cool things.").decode()
        return b

    mock_repo.get_git_blob.side_effect = fake_blob
    client = GitHubClient("test-token")

    summary = client.get_repo_summary("augusttollerup/myrepo")

    assert "CLAUDE.md" in summary
    assert "README.md" in summary
    assert "Project instructions" in summary
    assert "My Project" in summary
    assert "augusttollerup/myrepo" in summary
    assert summary.index("CLAUDE.md") < summary.index("README.md")


@patch("clients.github.Github")
def test_get_pr_reviews(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    from datetime import datetime, timezone
    submitted = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    mock_review = MagicMock()
    mock_review.id = 101
    mock_review.user.login = "reviewer-bot"
    mock_review.state = "APPROVED"
    mock_review.body = "Looks good!"
    mock_review.submitted_at = submitted
    mock_repo.get_pull.return_value.get_reviews.return_value = [mock_review]

    client = GitHubClient("test-token")
    reviews = client.get_pr_reviews("org/repo", 42)

    assert len(reviews) == 1
    assert reviews[0]["id"] == 101
    assert reviews[0]["user_login"] == "reviewer-bot"
    assert reviews[0]["state"] == "APPROVED"
    assert reviews[0]["body"] == "Looks good!"
    assert reviews[0]["submitted_at"] == submitted.isoformat()
    mock_repo.get_pull.assert_called_once_with(42)


@patch("clients.github.git.Repo")
@patch("clients.github.Github")
def test_checkout_branch(mock_github_class, mock_repo_class):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    client = GitHubClient("test-token")

    client.checkout_branch("/tmp/somerepo", "feature/my-branch")

    mock_repo.git.fetch.assert_called_once_with("origin")
    mock_repo.git.checkout.assert_called_once_with("feature/my-branch")


@patch("clients.github.Github")
def test_post_pr_comment(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    client = GitHubClient("test-token")

    client.post_pr_comment("org/repo", 7, "This is a comment")

    mock_repo.get_issue.assert_called_once_with(7)
    mock_repo.get_issue.return_value.create_comment.assert_called_once_with("This is a comment")


@patch("clients.github.Github")
def test_get_pr_check_status(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    mock_pr = MagicMock()
    mock_pr.head.sha = "abc123"
    mock_repo.get_pull.return_value = mock_pr
    mock_status = MagicMock()
    mock_status.state = "success"
    mock_repo.get_commit.return_value.get_combined_status.return_value = mock_status
    client = GitHubClient("test-token")

    state = client.get_pr_check_status("org/repo", 5)

    assert state == "success"
    mock_repo.get_commit.assert_called_once_with("abc123")


@patch("clients.github.Github")
def test_get_latest_review_timestamp_returns_none_when_no_reviews(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    mock_repo.get_pull.return_value.get_reviews.return_value = []
    client = GitHubClient("test-token")

    result = client.get_latest_review_timestamp("org/repo", 10, "my-bot")

    assert result is None


@patch("clients.github.Github")
def test_get_latest_review_timestamp_returns_latest(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    from datetime import datetime, timezone
    older = datetime(2024, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2024, 6, 1, tzinfo=timezone.utc)

    def make_review(login, submitted_at):
        r = MagicMock()
        r.user.login = login
        r.submitted_at = submitted_at
        return r

    mock_repo.get_pull.return_value.get_reviews.return_value = [
        make_review("my-bot", older),
        make_review("my-bot", newer),
        make_review("other-user", datetime(2024, 12, 1, tzinfo=timezone.utc)),
    ]
    client = GitHubClient("test-token")

    result = client.get_latest_review_timestamp("org/repo", 10, "my-bot")

    assert result == newer.isoformat()


@patch("clients.github.Github")
def test_get_latest_commit_timestamp(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    from datetime import datetime, timezone
    commit_date = datetime(2024, 3, 10, 8, 30, 0, tzinfo=timezone.utc)
    mock_pr = MagicMock()
    mock_pr.head.sha = "deadbeef"
    mock_pr.head.repo.get_commit.return_value.commit.author.date = commit_date
    mock_repo.get_pull.return_value = mock_pr
    client = GitHubClient("test-token")

    result = client.get_latest_commit_timestamp("org/repo", 3)

    assert result == commit_date.isoformat()
    mock_pr.head.repo.get_commit.assert_called_once_with("deadbeef")
