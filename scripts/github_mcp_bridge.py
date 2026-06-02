#!/usr/bin/env python3
"""Optional MCP bridge: read JSON from stdin, fetch PR via GitHubClient, print JSON.

Wire in .env:
  GITHUB_MCP_COMMAND=python scripts/github_mcp_bridge.py

Expected stdin:
  {"repo": "owner/name", "pr_number": 1}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pr_governance_agent.mcp.github_client import GitHubClient


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    repo = payload.get("repo", "dwgupta/migration-sandbox-capstone")
    pr_number = int(payload.get("pr_number", 1))
    pr_url = f"https://github.com/{repo}/pull/{pr_number}"
    data = GitHubClient().fetch_pr(pr_url)
    sys.stdout.write(json.dumps(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
