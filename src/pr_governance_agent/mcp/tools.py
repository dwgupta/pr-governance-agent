"""Thin wrappers around GitHubClient for LangGraph tool-style calls."""

from __future__ import annotations

from typing import Any

from pr_governance_agent.mcp.github_client import GitHubClient, parse_pr_url


def fetch_pull_request(pr_url: str) -> dict[str, Any]:
    """Load PR metadata, changed files, and truncated patches."""
    return GitHubClient().fetch_pr(pr_url)


def post_review_comment(repo: str, pr_number: int, body: str) -> str:
    """Post a review comment on the PR (or log in fixture mode)."""
    return GitHubClient().post_comment(repo, pr_number, body)


def approve_pull_request(repo: str, pr_number: int) -> str:
    """Submit an APPROVE review (gated by settings in graph nodes)."""
    return GitHubClient().approve_pr(repo, pr_number)


def merge_pull_request(repo: str, pr_number: int) -> str:
    """Merge the PR (gated by settings in graph nodes)."""
    return GitHubClient().merge_pr(repo, pr_number)


def parse_github_pr_url(pr_url: str) -> tuple[str, str, int]:
    """Return full_repo, repo_name, pr_number from a GitHub PR URL."""
    return parse_pr_url(pr_url)
