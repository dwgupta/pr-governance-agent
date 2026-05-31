#!/usr/bin/env python3
"""Run offline eval cases against the PR governance graph."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("USE_PR_FIXTURE", "true")

from pr_governance_agent.config import get_settings
from pr_governance_agent.graph.llm import FALLBACK_WARNING_PREFIX
from pr_governance_agent.graph.builder import compile_graph
from pr_governance_agent.state import initial_state


def _count_severity(findings: list, severities: set[str]) -> int:
    return sum(1 for f in findings if f.get("severity") in severities)


def _finding_messages(findings: list) -> str:
    return " ".join(f.get("message", "") for f in findings).lower()


def _has_llm_fallback(warnings: list[str]) -> bool:
    return any(FALLBACK_WARNING_PREFIX in w for w in warnings)


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
    warnings = result.get("warnings") or []
    all_findings = req_f + sec_f
    messages_blob = _finding_messages(all_findings)

    if case.get("expect_passed") is not None and passed != case["expect_passed"]:
        return False, f"expected passed={case['expect_passed']} got {passed}"

    if case.get("expect_risk") and risk != case["expect_risk"]:
        return False, f"expected risk={case['expect_risk']} got {risk}"

    allowed_risks = case.get("expect_risk_in") or []
    if allowed_risks and risk not in allowed_risks:
        return False, f"expected risk in {allowed_risks} got {risk}"

    if case.get("min_requirements_findings", 0) > len(req_f):
        return False, f"expected >={case['min_requirements_findings']} req findings, got {len(req_f)}"

    if case.get("min_security_findings", 0) > len(sec_f):
        return False, f"expected >={case['min_security_findings']} sec findings, got {len(sec_f)}"

    if case.get("max_critical_findings") is not None:
        crit = _count_severity(all_findings, {"critical"})
        if crit > case["max_critical_findings"]:
            return False, f"too many critical findings: {crit}"

    if case.get("max_high_findings") is not None:
        high = _count_severity(all_findings, {"high", "critical"})
        if high > case["max_high_findings"]:
            return False, f"too many high/critical findings: {high}"

    if case.get("forbid_llm_fallback") and _has_llm_fallback(warnings):
        return False, f"LLM fallback occurred: {warnings}"

    for token in case.get("forbid_finding_messages_containing") or []:
        if token.lower() in messages_blob:
            return False, f"forbidden finding message token present: {token}"

    required_any = case.get("require_finding_messages_containing_any") or []
    if required_any and not any(t.lower() in messages_blob for t in required_any):
        return False, f"missing required finding message token (any of {required_any})"

    joined = " ".join(actions).lower()
    for token in case.get("forbid_actions_containing") or []:
        if token.lower() in joined:
            return False, f"forbidden action token present: {token}"

    for token in case.get("require_actions_containing") or []:
        if token.lower() not in joined:
            return False, f"missing required action token: {token}"

    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PR governance eval cases")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Run LLM-mode cases (requires OPENAI_API_KEY; sets HEURISTIC_ONLY=false)",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        help="Path to cases YAML (default: eval/cases.yaml or eval/cases_llm.yaml with --llm)",
    )
    args = parser.parse_args()

    if args.llm:
        os.environ["HEURISTIC_ONLY"] = "false"
    else:
        os.environ["HEURISTIC_ONLY"] = "true"

    get_settings.cache_clear()
    settings = get_settings()

    cases_path = args.cases or (ROOT / "eval" / ("cases_llm.yaml" if args.llm else "cases.yaml"))
    if not cases_path.exists():
        print(f"Missing cases file: {cases_path}", file=sys.stderr)
        return 1

    if args.llm and not settings.llm_enabled:
        print(
            "Skipping LLM eval: OPENAI_API_KEY not set or HEURISTIC_ONLY=true.",
            file=sys.stderr,
        )
        return 0

    data = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    cases = data.get("cases", [])

    mode_label = "LLM" if args.llm else "heuristic"
    print(f"Running {len(cases)} {mode_label} eval case(s) from {cases_path.name}")

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
