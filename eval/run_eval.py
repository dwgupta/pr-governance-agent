#!/usr/bin/env python3
"""Run offline eval cases against the PR governance graph."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pr_governance_agent.graph.builder import compile_graph
from pr_governance_agent.state import initial_state

os.environ["USE_PR_FIXTURE"] = "true"
os.environ["HEURISTIC_ONLY"] = "true"  # deterministic eval


def _count_critical(findings: list) -> int:
    return sum(1 for f in findings if f.get("severity") == "critical")


def run_case(case: dict) -> tuple[bool, str]:
    fixture = ROOT / case["fixture"]
    if not fixture.exists():
        return False, f"Missing fixture: {fixture}"

    os.environ["PR_FIXTURE_PATH"] = str(fixture)
    data = json.loads(fixture.read_text(encoding="utf-8"))
    pr_url = data.get("pr_url", "https://github.com/demo/migration-sandbox/pull/1")

    app = compile_graph()
    state = initial_state(pr_url=pr_url, mode=case.get("mode", "advisory"))
    result = app.invoke(state, config={"configurable": {"thread_id": f"eval-{case['id']}"}})

    passed = result.get("passed")
    risk = result.get("overall_risk")
    actions = result.get("github_actions_taken") or []
    req_f = result.get("requirements_findings") or []
    sec_f = result.get("security_findings") or []

    if case.get("expect_passed") is not None and passed != case["expect_passed"]:
        return False, f"expected passed={case['expect_passed']} got {passed}"

    if case.get("expect_risk") and risk != case["expect_risk"]:
        return False, f"expected risk={case['expect_risk']} got {risk}"

    if case.get("min_requirements_findings", 0) > len(req_f):
        return False, f"expected >={case['min_requirements_findings']} req findings, got {len(req_f)}"

    if case.get("min_security_findings", 0) > len(sec_f):
        return False, f"expected >={case['min_security_findings']} sec findings, got {len(sec_f)}"

    if case.get("max_critical_findings") is not None:
        crit = _count_critical(req_f + sec_f)
        if crit > case["max_critical_findings"]:
            return False, f"too many critical findings: {crit}"

    joined = " ".join(actions).lower()
    for token in case.get("forbid_actions_containing") or []:
        if token.lower() in joined:
            return False, f"forbidden action token present: {token}"

    for token in case.get("require_actions_containing") or []:
        if token.lower() not in joined:
            return False, f"missing required action token: {token}"

    return True, "ok"


def main() -> int:
    cases_path = ROOT / "eval" / "cases.yaml"
    data = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    cases = data.get("cases", [])

    passed_count = 0
    for case in cases:
        ok, msg = run_case(case)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['id']}: {msg}")
        if ok:
            passed_count += 1

    print(f"\n{passed_count}/{len(cases)} cases passed")
    return 0 if passed_count == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
