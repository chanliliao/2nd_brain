"""
GitHub Integration
==================

Fetches open PRs (for review or authored) and assigned issues
via the GitHub API using a Personal Access Token (PAT).

Env var required:
  GITHUB_TOKEN -- GitHub PAT with repo + read:user scopes
  GITHUB_USERNAME -- optional; auto-detected from token if absent
"""

import sys
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass
class GitHubConfig:
    token: str
    username: Optional[str] = None

    @classmethod
    def from_env(cls) -> "GitHubConfig":
        load_dotenv()
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required.")
        username = os.getenv("GITHUB_USERNAME") or None
        return cls(token=token, username=username)


def _get_client(config: "GitHubConfig"):
    """Return authenticated PyGithub Github instance."""
    from github import Github
    return Github(config.token)


def _get_username(config: "GitHubConfig", g) -> str:
    """Return config.username if set, else authenticated user login."""
    if config.username:
        return config.username
    return g.get_user().login


def list_prs_for_review(config: "GitHubConfig") -> list:
    """Return PRs where the user is reviewer OR author, excluding drafts.

    Returns list of dicts with keys: number, title, repo, url, author,
    created_at, role ("reviewer" or "author").
    Deduplicates by (number, repo). Capped at 20 total.
    """
    g = _get_client(config)
    username = _get_username(config, g)
    seen = {}

    reviewer_query = f"is:pr is:open review-requested:{username} -is:draft"
    for item in g.search_issues(reviewer_query):
        key = (item.number, item.repository.full_name)
        if key not in seen:
            seen[key] = {
                "number": item.number,
                "title": item.title,
                "repo": item.repository.full_name,
                "url": item.html_url,
                "author": item.user.login,
                "created_at": item.created_at.isoformat(),
                "role": "reviewer",
            }

    author_query = f"is:pr is:open author:{username} -is:draft"
    for item in g.search_issues(author_query):
        key = (item.number, item.repository.full_name)
        if key not in seen:
            seen[key] = {
                "number": item.number,
                "title": item.title,
                "repo": item.repository.full_name,
                "url": item.html_url,
                "author": item.user.login,
                "created_at": item.created_at.isoformat(),
                "role": "author",
            }

    return list(seen.values())[:20]


def list_issues_assigned(config: "GitHubConfig") -> list:
    """Return open issues assigned to the user.

    Returns list of dicts: number, title, repo, url, created_at.
    Capped at 20.
    """
    g = _get_client(config)
    username = _get_username(config, g)
    query = f"is:issue is:open assignee:{username}"
    results = []
    for item in g.search_issues(query):
        results.append({
            "number": item.number,
            "title": item.title,
            "repo": item.repository.full_name,
            "url": item.html_url,
            "created_at": item.created_at.isoformat(),
        })
        if len(results) >= 20:
            break
    return results


def pr_diff(config: "GitHubConfig", repo_name: str, pr_number: int) -> str:
    """Return unified diff for a PR, truncated to 4000 chars if longer.

    repo_name: "owner/repo" format. Skips binary files (patch is None).
    """
    g = _get_client(config)
    repo = g.get_repo(repo_name)
    pull = repo.get_pull(pr_number)
    parts = []
    for f in pull.get_files():
        if f.patch is None:
            continue
        header = "--- a/" + f.filename + "\n" + "+++ b/" + f.filename + "\n"
        parts.append(header + f.patch)
    diff = "\n\n".join(parts)
    if len(diff) > 4000:
        diff = diff[:4000]
    return diff


def format_context(prs: list) -> str:
    """Return plain-text summary of PRs for LLM context injection.

    Format:
      GITHUB PRs ({n} items):
      - #{number} [{role}] {title} in {repo} ({url})
    """
    n = len(prs)
    if n == 0:
        return "GITHUB PRs (0 items):\n(none)"
    out = [f"GITHUB PRs ({n} items):"]
    for pr in prs:
        role = pr.get("role", "author")
        out.append(
            "- #" + str(pr["number"]) + " [" + role + "] " + pr["title"]
            + " in " + pr["repo"] + " (" + pr["url"] + ")"
        )
    return "\n".join(out)


def cli_dispatch(args: list) -> None:
    """CLI: prs | issues | diff OWNER/REPO PR_NUMBER"""
    if not args:
        print("Usage: github.py prs | issues | diff OWNER/REPO PR_NUMBER")
        return
    command = args[0]
    if command == "prs":
        config = GitHubConfig.from_env()
        prs = list_prs_for_review(config)
        print(format_context(prs))
    elif command == "issues":
        config = GitHubConfig.from_env()
        issues = list_issues_assigned(config)
        n = len(issues)
        if n == 0:
            print("GITHUB Issues (0 items):\n(none)")
            return
        out = [f"GITHUB Issues ({n} items):"]
        for issue in issues:
            out.append(
                "- #" + str(issue["number"]) + " " + issue["title"]
                + " in " + issue["repo"] + " (" + issue["url"] + ")"
            )
        print("\n".join(out))
    elif command == "diff":
        if len(args) < 3:
            print("Usage: github.py diff OWNER/REPO PR_NUMBER")
            return
        config = GitHubConfig.from_env()
        repo_name = args[1]
        pr_number = int(args[2])
        print(pr_diff(config, repo_name, pr_number))
    else:
        print("Usage: github.py prs | issues | diff OWNER/REPO PR_NUMBER")


if __name__ == "__main__":
    cli_dispatch(sys.argv[1:])
