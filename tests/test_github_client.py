import os
import tempfile
from unittest.mock import MagicMock, patch, call
import pytest
from github_client import clone_repo, create_branch, commit_and_push, create_pr


@patch("github_client.git.Repo.clone_from")
def test_clone_repo_returns_path(mock_clone):
    mock_clone.return_value = MagicMock()
    path = clone_repo("augusttollerup/myrepo")
    assert os.path.isabs(path)
    assert mock_clone.called
    url = mock_clone.call_args[0][0]
    assert "augusttollerup/myrepo" in url


@patch("github_client.git.Repo")
def test_create_branch(mock_repo_class):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    create_branch("/tmp/somerepo", "agent/asana-111-fix-login")

    mock_repo.git.checkout.assert_called_once_with("-b", "agent/asana-111-fix-login")


@patch("github_client.git.Repo")
def test_commit_and_push(mock_repo_class):
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    commit_and_push("/tmp/somerepo", "agent/asana-111-fix-login", "fix: resolve login bug")

    mock_repo.git.add.assert_called_once_with("--all")
    mock_repo.index.commit.assert_called_once_with("fix: resolve login bug")
    mock_repo.git.push.assert_called_once_with("--set-upstream", "origin", "agent/asana-111-fix-login")


@patch("github_client.Github")
def test_create_pr_returns_url(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    mock_pr = MagicMock()
    mock_pr.html_url = "https://github.com/augusttollerup/myrepo/pull/42"
    mock_repo.create_pull.return_value = mock_pr

    url = create_pr(
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
