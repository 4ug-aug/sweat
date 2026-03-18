import base64
import os
from datetime import datetime, timedelta, timezone
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
    mock_commit = mock_repo.get_commit.return_value
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_run.conclusion = "success"
    mock_commit.get_check_runs.return_value = [mock_run]
    client = GitHubClient("test-token")

    state = client.get_pr_check_status("org/repo", 5)

    assert state == "success"
    mock_repo.get_commit.assert_called_once_with("abc123")


@patch("clients.github.Github")
def test_get_pr_check_status_pending_when_run_in_progress(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    mock_pr = MagicMock()
    mock_pr.head.sha = "abc123"
    mock_repo.get_pull.return_value = mock_pr
    mock_commit = mock_repo.get_commit.return_value
    mock_run = MagicMock()
    mock_run.status = "in_progress"
    mock_run.conclusion = None
    mock_commit.get_check_runs.return_value = [mock_run]

    client = GitHubClient("test-token")
    state = client.get_pr_check_status("org/repo", 5)

    assert state == "pending"


@patch("clients.github.Github")
def test_get_pr_check_status_failure_when_run_failed(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    mock_pr = MagicMock()
    mock_pr.head.sha = "abc123"
    mock_repo.get_pull.return_value = mock_pr
    mock_commit = mock_repo.get_commit.return_value
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_run.conclusion = "failure"
    mock_commit.get_check_runs.return_value = [mock_run]

    client = GitHubClient("test-token")
    state = client.get_pr_check_status("org/repo", 5)

    assert state == "failure"


@patch("clients.github.Github")
def test_get_pr_check_status_falls_back_to_combined_status(mock_github_class):
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    mock_pr = MagicMock()
    mock_pr.head.sha = "abc123"
    mock_repo.get_pull.return_value = mock_pr
    mock_commit = mock_repo.get_commit.return_value
    mock_commit.get_check_runs.return_value = []
    mock_status = MagicMock()
    mock_status.state = "success"
    mock_commit.get_combined_status.return_value = mock_status

    client = GitHubClient("test-token")
    state = client.get_pr_check_status("org/repo", 5)

    assert state == "success"


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


# --- GitHub App mode tests ---

def _make_app_client(mock_github_class, mock_integration_class):
    """Helper: create an app-mode GitHubClient with mocked Github and GithubIntegration."""
    mock_gh = MagicMock()
    mock_github_class.return_value = mock_gh
    mock_integration = MagicMock()
    mock_integration_class.return_value = mock_integration
    client = GitHubClient(app_id="12345", private_key="-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----")
    return client, mock_gh, mock_integration


@patch("clients.github.GithubIntegration")
@patch("clients.github.Github")
def test_app_mode_get_bot_login_returns_slug(mock_github_class, mock_integration_class):
    client, mock_gh, _ = _make_app_client(mock_github_class, mock_integration_class)
    mock_gh.get_app.return_value.slug = "my-app"

    login = client.get_bot_login()

    assert login == "my-app[bot]"
    mock_gh.get_app.return_value.get_user = MagicMock()  # should not be called
    mock_gh.get_user.assert_not_called()


@patch("clients.github.GithubIntegration")
@patch("clients.github.Github")
def test_app_mode_token_for_owner_cache_miss(mock_github_class, mock_integration_class):
    client, mock_gh, mock_integration = _make_app_client(mock_github_class, mock_integration_class)

    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_inst = MagicMock()
    mock_inst.account.login = "myorg"
    mock_inst.id = 99
    mock_integration.get_installations.return_value = [mock_inst]
    mock_access = MagicMock()
    mock_access.token = "inst-token-abc"
    mock_access.expires_at = expires_at
    mock_integration.get_access_token.return_value = mock_access

    token = client._token_for_owner("myorg")

    assert token == "inst-token-abc"
    mock_integration.get_access_token.assert_called_once_with(99)
    assert client._install_cache["myorg"] == ("inst-token-abc", expires_at)


@patch("clients.github.GithubIntegration")
@patch("clients.github.Github")
def test_app_mode_token_for_owner_cache_hit(mock_github_class, mock_integration_class):
    client, mock_gh, mock_integration = _make_app_client(mock_github_class, mock_integration_class)

    future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    client._install_cache["myorg"] = ("cached-token", future_expiry)

    token = client._token_for_owner("myorg")

    assert token == "cached-token"
    mock_integration.get_access_token.assert_not_called()


@patch("clients.github.GithubIntegration")
@patch("clients.github.Github")
def test_app_mode_token_for_owner_near_expiry_refreshes(mock_github_class, mock_integration_class):
    client, mock_gh, mock_integration = _make_app_client(mock_github_class, mock_integration_class)

    # Near-expired: expires in 3 minutes (< 5 min threshold)
    near_expiry = datetime.now(timezone.utc) + timedelta(minutes=3)
    client._install_cache["myorg"] = ("old-token", near_expiry)

    new_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_inst = MagicMock()
    mock_inst.account.login = "myorg"
    mock_inst.id = 42
    mock_integration.get_installations.return_value = [mock_inst]
    mock_access = MagicMock()
    mock_access.token = "fresh-token"
    mock_access.expires_at = new_expiry
    mock_integration.get_access_token.return_value = mock_access

    token = client._token_for_owner("myorg")

    assert token == "fresh-token"
    mock_integration.get_access_token.assert_called_once_with(42)


@patch("clients.github.GithubIntegration")
@patch("clients.github.Github")
def test_app_mode_token_for_owner_not_found_raises(mock_github_class, mock_integration_class):
    client, mock_gh, mock_integration = _make_app_client(mock_github_class, mock_integration_class)
    mock_inst = MagicMock()
    mock_inst.account.login = "otherorg"
    mock_integration.get_installations.return_value = [mock_inst]

    with pytest.raises(ValueError, match="No GitHub App installation found for owner: myorg"):
        client._token_for_owner("myorg")


@patch("clients.github.tempfile.mkdtemp")
@patch("clients.github.git.Repo.clone_from")
@patch("clients.github.GithubIntegration")
@patch("clients.github.Github")
def test_app_mode_clone_repo_uses_installation_token(mock_github_class, mock_integration_class, mock_clone, mock_mkdtemp):
    mock_mkdtemp.return_value = "/tmp/sweat_apptest"
    mock_clone.return_value = MagicMock()
    client, mock_gh, mock_integration = _make_app_client(mock_github_class, mock_integration_class)

    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_inst = MagicMock()
    mock_inst.account.login = "myorg"
    mock_inst.id = 7
    mock_integration.get_installations.return_value = [mock_inst]
    mock_access = MagicMock()
    mock_access.token = "install-token-xyz"
    mock_access.expires_at = expires_at
    mock_integration.get_access_token.return_value = mock_access

    path = client.clone_repo("myorg/myrepo")

    assert path == "/tmp/sweat_apptest"
    url = mock_clone.call_args[0][0]
    assert "install-token-xyz" in url
    assert "myorg/myrepo" in url
