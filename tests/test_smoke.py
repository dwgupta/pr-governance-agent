"""Smoke tests for PR governance agent (offline fixtures)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("USE_PR_FIXTURE", "true")
os.environ["HEURISTIC_ONLY"] = "true"
os.environ["PR_FIXTURE_PATH"] = str(ROOT / "eval" / "fixtures" / "sample_pr.json")


@pytest.fixture
def app():
    from pr_governance_agent.graph.builder import compile_graph

    return compile_graph()


def test_parse_pr_url():
    from pr_governance_agent.mcp.github_client import parse_pr_url

    full, name, num = parse_pr_url("https://github.com/acme/repo/pull/99")
    assert full == "acme/repo"
    assert name == "repo"
    assert num == 99


def test_graph_invoke_clean_pr(app):
    from pr_governance_agent.state import initial_state

    state = initial_state(
        pr_url="https://github.com/demo/migration-sandbox/pull/1",
        mode="advisory",
    )
    result = app.invoke(state, config={"configurable": {"thread_id": "test-clean"}})
    assert result.get("review_markdown")
    assert result.get("passed") is True
    assert result.get("overall_risk") == "low"


def test_graph_detects_dialect_violation(app):
    from pr_governance_agent.state import initial_state

    os.environ["PR_FIXTURE_PATH"] = str(
        ROOT / "eval" / "fixtures" / "pr_dialect_violation.json"
    )
    state = initial_state(
        pr_url="https://github.com/demo/migration-sandbox/pull/2",
        mode="advisory",
    )
    result = app.invoke(state, config={"configurable": {"thread_id": "test-dialect"}})
    assert result.get("passed") is False
    assert result.get("overall_risk") in ("high", "blocked")
    findings = result.get("requirements_findings") or []
    assert len(findings) >= 1


def test_chroma_store_query():
    from pr_governance_agent.rag.chroma_store import REQUIREMENTS_COLLECTION, ChromaStore

    store = ChromaStore()
    if store.get_or_create_collection(REQUIREMENTS_COLLECTION).count() == 0:
        pytest.skip("Run scripts/ingest_docs.py first")

    chunks = store.retrieve(
        REQUIREMENTS_COLLECTION,
        "partition event_date BigQuery",
        retrieve_n=10,
        top_k=3,
        enable_rerank=False,
    )
    assert len(chunks) >= 1
    assert chunks[0]["text"]
    assert "BigQuery Migration Engineering Requirements" in chunks[0]["text"] or "event_date" in chunks[0]["text"]
