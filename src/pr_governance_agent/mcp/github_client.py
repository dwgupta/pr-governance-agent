"""GitHub PR access via REST API with optional MCP command hook and fixture fallback."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx

from pr_governance_agent.config import ROOT_DIR, get_settings

PR_URL_PATTERN = re.compile(
    r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)",
    re.I,
)


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """Parse GitHub PR URL into (owner/repo, repo_name, pr_number)."""
    match = PR_URL_PATTERN.search(pr_url)
    if not match:
        raise ValueError(f"Invalid GitHub PR URL: {pr_url}")
    owner = match.group("owner")
    repo = match.group("repo")
    number = int(match.group("number"))
    return f"{owner}/{repo}", repo, number


def _fixture_path() -> Path:
    return ROOT_DIR / "eval" / "fixtures" / "sample_pr.json"


class GitHubClient:
    """Fetch and mutate PRs via REST, fixtures, or an optional MCP shell command."""

    def __init__(self, token: str | None = None) -> None:
        settings = get_settings()
        self._token = token or settings.github_token
        self._use_fixture = settings.use_pr_fixture
        self._mcp_command = settings.github_mcp_command.strip()
        self._max_files = settings.max_diff_files
        self._max_lines = settings.max_diff_lines

    def fetch_pr(self, pr_url: str) -> dict[str, Any]:
        """Return PR payload: metadata, changed_files, patches (fixture → MCP → REST)."""
        if self._use_fixture or not self._token:
            return self._load_fixture(pr_url)

        if self._mcp_command:
            try:
                return self._fetch_via_mcp(pr_url)
            except Exception:
                pass

        return self._fetch_via_rest(pr_url)

    def _load_fixture(self, pr_url: str) -> dict[str, Any]:
        override = os.environ.get("PR_FIXTURE_PATH", "").strip()
        path = Path(override) if override else _fixture_path()
        if not path.exists():
            raise FileNotFoundError(f"PR fixture not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if pr_url and PR_URL_PATTERN.search(pr_url):
            full_repo, _, number = parse_pr_url(pr_url)
            data["repo"] = full_repo
            data["pr_number"] = number
        data["pr_url"] = pr_url or data.get("pr_url", "")
        return data

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _fetch_via_rest(self, pr_url: str) -> dict[str, Any]:
        full_repo, repo_name, pr_number = parse_pr_url(pr_url)
        owner = full_repo.split("/")[0]
        base = f"https://api.github.com/repos/{full_repo}"

        with httpx.Client(timeout=60.0) as client:
            pr_resp = client.get(f"{base}/pulls/{pr_number}", headers=self._headers())
            pr_resp.raise_for_status()
            pr_data = pr_resp.json()

            files_resp = client.get(
                f"{base}/pulls/{pr_number}/files",
                headers=self._headers(),
                params={"per_page": 100},
            )
            files_resp.raise_for_status()
            files_data = files_resp.json()

        changed_files: list[str] = []
        patches: list[dict[str, Any]] = []
        line_count = 0

        for f in files_data[: self._max_files]:
            filename = f.get("filename", "")
            patch = f.get("patch") or ""
            patch_lines = patch.splitlines()
            # Truncate total diff lines to stay within LLM/context limits
            if line_count + len(patch_lines) > self._max_lines:
                remaining = max(self._max_lines - line_count, 0)
                patch = "\n".join(patch_lines[:remaining]) + "\n... [truncated]"
            line_count += len(patch.splitlines())
            changed_files.append(filename)
            patches.append(
                {
                    "filename": filename,
                    "status": f.get("status"),
                    "patch": patch,
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                }
            )

        return {
            "pr_url": pr_url,
            "repo": full_repo,
            "pr_number": pr_number,
            "pr_metadata": {
                "title": pr_data.get("title"),
                "body": pr_data.get("body"),
                "state": pr_data.get("state"),
                "merged": bool(pr_data.get("merged")),
                "merged_at": pr_data.get("merged_at"),
                "user": (pr_data.get("user") or {}).get("login"),
                "base": (pr_data.get("base") or {}).get("ref"),
                "head": (pr_data.get("head") or {}).get("ref"),
            },
            "changed_files": changed_files,
            "patches": patches,
            "ci_status": None,
        }

    def _fetch_via_mcp(self, pr_url: str) -> dict[str, Any]:
        """Optional MCP bridge: expects JSON on stdout from a wrapper script."""
        full_repo, _, pr_number = parse_pr_url(pr_url)
        payload = json.dumps({"repo": full_repo, "pr_number": pr_number})
        result = subprocess.run(
            self._mcp_command,
            shell=True,
            input=payload,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or "MCP command failed")
        return json.loads(result.stdout)

    def post_comment(self, repo: str, pr_number: int, body: str) -> str:
        settings = get_settings()
        if self._use_fixture or not self._token:
            return "comment_logged_fixture"

        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=self._headers(), json={"body": body})
            resp.raise_for_status()
        return "comment_posted"

    def approve_pr(self, repo: str, pr_number: int) -> str:
        if self._use_fixture or not self._token:
            return "approve_logged_fixture"
        owner, name = repo.split("/", 1)
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                url,
                headers=self._headers(),
                json={"event": "APPROVE", "body": "Approved by PR Governance Agent (POC)."},
            )
            resp.raise_for_status()
        return "approved"

    def merge_pr(self, repo: str, pr_number: int) -> str:
        if self._use_fixture or not self._token:
            return "merge_logged_fixture"
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/merge"
        with httpx.Client(timeout=30.0) as client:
            resp = client.put(
                url,
                headers=self._headers(),
                json={"merge_method": "squash"},
            )
            resp.raise_for_status()
        return "merged"
