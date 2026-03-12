from prompts.review_prompt import build_review_prompt


def _make_meta(**kwargs):
    base = {
        "number": 1,
        "title": "Add login feature",
        "body": "Implements OAuth login",
        "author_login": "alice",
        "head_branch": "feat/login",
        "base_branch": "main",
        "html_url": "https://github.com/org/repo/pull/1",
    }
    base.update(kwargs)
    return base


def test_prompt_contains_title():
    prompt = build_review_prompt(_make_meta(), "some diff", "repo context")
    assert "Add login feature" in prompt


def test_prompt_contains_diff():
    prompt = build_review_prompt(_make_meta(), "--- file.py\n+added line", "repo context")
    assert "--- file.py" in prompt
    assert "+added line" in prompt


def test_prompt_contains_repo_context():
    prompt = build_review_prompt(_make_meta(), "diff", "## File tree\nfoo.py\nbar.py")
    assert "## File tree" in prompt
    assert "foo.py" in prompt


def test_prompt_contains_output_sections():
    prompt = build_review_prompt(_make_meta(), "diff", "context")
    assert "### Summary" in prompt
    assert "### Concerns" in prompt
    assert "### Suggestions" in prompt
    assert "### Verdict" in prompt


def test_prompt_contains_author_and_branch():
    prompt = build_review_prompt(_make_meta(), "diff", "context")
    assert "alice" in prompt
    assert "feat/login" in prompt
    assert "main" in prompt
