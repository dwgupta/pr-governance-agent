#!/usr/bin/env python3
"""Run the PR governance graph from the command line."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pr_governance_agent.config import get_settings

# Apply LangSmith tracing env before any LangChain import
get_settings()

from pr_governance_agent.graph.builder import compile_graph
from pr_governance_agent.state import initial_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PR governance agent graph")
    parser.add_argument(
        "--pr-url",
        default="https://github.com/dwgupta/migration-sandbox-capstone/pull/1",
        help="GitHub PR URL (or use USE_PR_FIXTURE=true)",
    )
    parser.add_argument(
        "--mode",
        choices=["advisory", "auto"],
        default="advisory",
    )
    parser.add_argument("--json", action="store_true", help="Print full state as JSON")
    parser.add_argument(
        "--heuristic-only",
        action="store_true",
        help="Skip LLM; use rule-based checks only",
    )
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="Exit 0 even when review fails (useful in CI smoke)",
    )
    args = parser.parse_args()

    if args.heuristic_only:
        os.environ["HEURISTIC_ONLY"] = "true"

    app = compile_graph()
    state = initial_state(pr_url=args.pr_url, mode=args.mode)
    result = app.invoke(state, config={"configurable": {"thread_id": "cli-run"}})

    if args.json:
        print(json.dumps(dict(result), indent=2, default=str))
    else:
        print(result.get("review_markdown", ""))
        print("\n---")
        print(f"Passed: {result.get('passed')} | Risk: {result.get('overall_risk')}")
        print(f"Actions: {result.get('github_actions_taken')}")
        if result.get("blockers"):
            print(f"Blockers: {result.get('blockers')}")
        if result.get("warnings"):
            print(f"Warnings: {result.get('warnings')}")
        if result.get("errors"):
            print(f"Errors: {result.get('errors')}")

    if args.exit_zero:
        return 0
    return 0 if result.get("passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
