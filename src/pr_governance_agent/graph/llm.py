from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from pr_governance_agent.config import get_settings
from pr_governance_agent.state import Finding, PRReviewState, RetrievalChunk


def _get_llm() -> ChatOpenAI | None:
    settings = get_settings()
    if not settings.llm_enabled:
        return None
    kwargs: dict[str, Any] = {
        "model": settings.openai_model,
        "api_key": settings.openai_api_key,
        "temperature": 0,
    }
    if settings.openai_api_base:
        kwargs["base_url"] = settings.openai_api_base
    return ChatOpenAI(**kwargs)


def _heuristic_requirements(state: PRReviewState) -> list[Finding]:
    findings: list[Finding] = []
    oracle_patterns = [
        (r"\bROWNUM\b", "Oracle ROWNUM detected; use BigQuery-compatible patterns"),
        (r"\(\+\)", "Oracle outer-join (+) syntax detected"),
        (r"SELECT\s+\*", "SELECT * may violate cost control policy"),
    ]
    for patch in state.get("patches") or []:
        text = patch.get("patch") or ""
        fname = patch.get("filename", "")
        for pattern, msg in oracle_patterns:
            if re.search(pattern, text, re.I):
                findings.append(
                    Finding(
                        severity="high",
                        category="requirements",
                        message=msg,
                        file=fname,
                        citation="heuristic:dialect",
                    )
                )
    return findings


def _heuristic_security(state: PRReviewState) -> list[Finding]:
    findings: list[Finding] = []
    pii_patterns = [
        (r"\bssn\b", "Possible raw SSN field"),
        (r"\bemail\b", "Possible raw email PII column"),
        (r"password\s*=", "Hardcoded password assignment"),
        (r"api[_-]?key\s*=", "Possible hardcoded API key"),
    ]
    for patch in state.get("patches") or []:
        text = patch.get("patch") or ""
        fname = patch.get("filename", "")
        for pattern, msg in pii_patterns:
            if re.search(pattern, text, re.I):
                findings.append(
                    Finding(
                        severity="critical",
                        category="security",
                        message=msg,
                        file=fname,
                        citation="heuristic:pii",
                    )
                )
    body = (state.get("pr_metadata") or {}).get("body") or ""
    if re.search(r"no\s+pii", body, re.I):
        for f in findings:
            if "email" in f["message"].lower() or "ssn" in f["message"].lower():
                f["message"] += " (contradicts PR description claiming no PII)"
    return findings


def evaluate_with_llm_or_heuristic(
    state: PRReviewState,
    kind: str,
    chunks: list[RetrievalChunk],
) -> list[Finding]:
    llm = _get_llm()
    if llm is None:
        if kind == "requirements":
            return _heuristic_requirements(state)
        return _heuristic_security(state)

    context = "\n\n".join(
        f"[{c['source']} / {c['section']}]\n{c['text']}" for c in chunks[:5]
    )
    diff_summary = "\n".join(
        f"{p.get('filename')}: {len((p.get('patch') or '').splitlines())} diff lines"
        for p in (state.get("patches") or [])[:10]
    )
    system = (
        "You are a data engineering governance reviewer. "
        "Return JSON array of findings with keys: severity (low|medium|high|critical), "
        "category, message, file, citation. Only cite provided policy chunks."
    )
    human = f"Review type: {kind}\n\nPolicies:\n{context}\n\nPR files:\n{diff_summary}\n\n"
    patches = json.dumps(
        [{"file": p.get("filename"), "patch": (p.get("patch") or "")[:2000]} for p in state.get("patches", [])[:5]]
    )
    human += f"Patches sample:\n{patches}"

    try:
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        usage = state.get("token_usage") or {}
        usage[kind] = usage.get(kind, 0) + 1
        state["token_usage"] = usage
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            raise ValueError("No JSON array in response")
        raw = json.loads(match.group())
        return [
            Finding(
                severity=item.get("severity", "medium"),
                category=item.get("category", kind),
                message=item.get("message", ""),
                file=item.get("file", ""),
                citation=item.get("citation", ""),
            )
            for item in raw
        ]
    except Exception:
        if kind == "requirements":
            return _heuristic_requirements(state)
        return _heuristic_security(state)
