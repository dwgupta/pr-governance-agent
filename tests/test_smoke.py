"""Smoke tests for PR governance agent (offline fixtures)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("USE_PR_FIXTURE", "true")
os.environ["HEURISTIC_ONLY"] = "true"
os.environ.setdefault("RAG_RERANK_ENABLED", "true")
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
    req_chunks = result.get("requirements_chunks") or []
    if req_chunks:
        assert "vector_score" in req_chunks[0], "RAG reranking should run on graph invoke"


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
    )
    assert len(chunks) >= 1
    assert chunks[0]["text"]
    assert "vector_score" in chunks[0], "reranking should set vector_score on chunks"
    assert "BigQuery Migration Engineering Requirements" in chunks[0]["text"] or "event_date" in chunks[0]["text"]


def test_empty_chroma_index_warns(app, tmp_path, monkeypatch):
    from pr_governance_agent.config import get_settings
    from pr_governance_agent.state import initial_state

    empty_chroma = tmp_path / "empty_chroma"
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(empty_chroma))
    get_settings.cache_clear()

    state = initial_state(
        pr_url="https://github.com/demo/migration-sandbox/pull/1",
        mode="advisory",
    )
    result = app.invoke(state, config={"configurable": {"thread_id": "test-empty-chroma"}})

    warnings = result.get("warnings") or []
    assert warnings
    assert any("ingest_docs.py" in w for w in warnings)
    assert "ingest_docs.py" in (result.get("review_markdown") or "")
