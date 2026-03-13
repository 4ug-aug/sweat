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
