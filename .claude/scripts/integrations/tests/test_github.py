"""
Tests for the GitHub integration module.
"""
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Make sure the integrations package is importable
sys.path.insert(0, str(__file__).split(".claude")[0] + ".claude/scripts")

from integrations.github import (
    GitHubConfig,
    format_context,
    list_prs_for_review,
    pr_diff,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(number, title, repo_full, html_url, login, created_at, draft=False):
    """Build a mock PyGithub issue/PR search result."""
    item = MagicMock()
    item.number = number
    item.title = title
    item.html_url = html_url
    item.user.login = login
    item.created_at = datetime.fromisoformat(created_at)
    item.pull_request = MagicMock()
    item.pull_request.draft = draft
    item.repository.full_name = repo_full
    return item


def _make_file(filename, patch=None):
    """Build a mock PyGithub File object."""
    f = MagicMock()
    f.filename = filename
    f.patch = patch
    return f


# ---------------------------------------------------------------------------
# format_context tests
# ---------------------------------------------------------------------------

def test_format_context_empty():
    result = format_context([])
    assert "0 items" in result
    assert "none" in result.lower()


def test_format_context_with_pr():
    prs = [{
        "number": 42,
        "title": "Fix the thing",
        "repo": "owner/repo",
        "url": "https://github.com/owner/repo/pull/42",
        "author": "henry",
        "created_at": "2024-04-23T10:00:00",
        "role": "reviewer",
    }]
    result = format_context(prs)
    assert "#42" in result
    assert "[reviewer]" in result
    assert "Fix the thing" in result
    assert "owner/repo" in result
    assert "https://github.com/owner/repo/pull/42" in result


# ---------------------------------------------------------------------------
# list_prs_for_review — deduplication test
# ---------------------------------------------------------------------------

def test_list_prs_deduplicates():
    """Same PR returned by both reviewer and author queries should appear once."""
    config = GitHubConfig(token="fake-token", username="henry")

    pr = _make_issue(
        number=7,
        title="Shared PR",
        repo_full="owner/repo",
        html_url="https://github.com/owner/repo/pull/7",
        login="henry",
        created_at="2024-04-23T09:00:00",
    )

    mock_g = MagicMock()
    # Both search queries return the same PR
    mock_g.search_issues.return_value = [pr]

    with patch("integrations.github._get_client", return_value=mock_g):
        results = list_prs_for_review(config)

    assert len(results) == 1


# ---------------------------------------------------------------------------
# pr_diff tests
# ---------------------------------------------------------------------------

def test_pr_diff_truncates():
    """Diffs longer than 4000 chars should be truncated."""
    config = GitHubConfig(token="fake-token", username="henry")

    long_patch = "+ " + "x" * 5000
    mock_file = _make_file("big_file.py", patch=long_patch)

    mock_pull = MagicMock()
    mock_pull.get_files.return_value = [mock_file]

    mock_repo = MagicMock()
    mock_repo.get_pull.return_value = mock_pull

    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    with patch("integrations.github._get_client", return_value=mock_g):
        result = pr_diff(config, "owner/repo", 1)

    assert len(result) <= 4000


def test_pr_diff_skips_binary_files():
    """Files with patch=None (binary) should not appear in the diff output."""
    config = GitHubConfig(token="fake-token", username="henry")

    binary_file = _make_file("image.png", patch=None)
    text_file = _make_file("main.py", patch="+ new line")

    mock_pull = MagicMock()
    mock_pull.get_files.return_value = [binary_file, text_file]

    mock_repo = MagicMock()
    mock_repo.get_pull.return_value = mock_pull

    mock_g = MagicMock()
    mock_g.get_repo.return_value = mock_repo

    with patch("integrations.github._get_client", return_value=mock_g):
        result = pr_diff(config, "owner/repo", 1)

    assert "image.png" not in result
    assert "main.py" in result
