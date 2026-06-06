"""End-to-end smoke tests: graph invoke, RAG, empty Chroma warnings.

Uses offline fixtures (USE_PR_FIXTURE) and heuristic mode for deterministic CI.
"""

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
        pr_url="https://github.com/dwgupta/migration-sandbox-capstone/pull/1",
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
        pr_url="https://github.com/dwgupta/migration-sandbox-capstone/pull/2",
        mode="advisory",
    )
    result = app.invoke(state, config={"configurable": {"thread_id": "test-dialect"}})
    assert result.get("passed") is False
    assert result.get("overall_risk") in ("high", "blocked")
    findings = result.get("requirements_findings") or []
    assert len(findings) >= 1


def test_graph_detects_invalid_bigquery_syntax(app, monkeypatch):
    from pr_governance_agent.state import initial_state

    monkeypatch.setenv(
        "PR_FIXTURE_PATH",
        str(ROOT / "eval" / "fixtures" / "pr_invalid_bq_syntax.json"),
    )
    state = initial_state(
        pr_url="https://github.com/dwgupta/migration-sandbox-capstone/pull/3",
        mode="advisory",
    )
    result = app.invoke(state, config={"configurable": {"thread_id": "test-bq-syntax"}})
    assert result.get("passed") is False
    assert result.get("overall_risk") in ("high", "blocked")
    findings = result.get("requirements_findings") or []
    assert any(f.get("category") == "sql_syntax" for f in findings)


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
        pr_url="https://github.com/dwgupta/migration-sandbox-capstone/pull/1",
        mode="advisory",
    )
    result = app.invoke(state, config={"configurable": {"thread_id": "test-empty-chroma"}})

    warnings = result.get("warnings") or []
    assert warnings
    assert any("ingest_docs.py" in w for w in warnings)
    assert "ingest_docs.py" in (result.get("review_markdown") or "")


def test_route_decision_fail_closed_on_ingest_error():
    from pr_governance_agent.graph import nodes
    from pr_governance_agent.state import initial_state

    state = initial_state(
        pr_url="https://github.com/dwgupta/migration-sandbox-capstone/pull/99999",
        mode="advisory",
    )
    state["errors"] = [
        "ingest_pr: Client error '404 Not Found' for url 'https://api.github.com/repos/dwgupta/migration-sandbox-capstone/pulls/99999'"
    ]
    state["requirements_findings"] = []
    state["security_findings"] = []

    result = nodes.route_decision(state)
    assert result.get("passed") is False
    assert result.get("overall_risk") == "blocked"
    assert "PR ingest failed; cannot evaluate governance safely" in (
        result.get("blockers") or []
    )


def test_execute_github_auto_skips_self_approval_and_merges(monkeypatch):
    from pr_governance_agent.graph import nodes
    from pr_governance_agent.state import initial_state

    class FakeClient:
        def approve_pr(self, repo: str, pr_number: int) -> str:
            raise RuntimeError(
                "Client error '422 Unprocessable Entity' ... "
                "Review Can not approve your own pull request"
            )

        def merge_pr(self, repo: str, pr_number: int) -> str:
            return "merged"

    monkeypatch.setattr(nodes, "GitHubClient", FakeClient)
    monkeypatch.setenv("ALLOW_WRITE_ACTIONS", "true")
    monkeypatch.setenv("SANDBOX_REPO", "dwgupta/migration-sandbox-capstone")
    from pr_governance_agent.config import get_settings

    get_settings.cache_clear()

    state = initial_state(
        pr_url="https://github.com/dwgupta/migration-sandbox-capstone/pull/1",
        mode="auto",
        repo="dwgupta/migration-sandbox-capstone",
        pr_number=1,
    )
    state["passed"] = True
    state["github_actions_taken"] = ["advisory_review_generated"]

    result = nodes.execute_github_auto(state)
    actions = result.get("github_actions_taken") or []
    assert "approve_skipped_self_author" in actions
    assert "merged" in actions
    assert not result.get("errors")


def test_execute_github_auto_skips_already_merged_pr(monkeypatch):
    from pr_governance_agent.graph import nodes
    from pr_governance_agent.state import initial_state

    class FakeClient:
        def approve_pr(self, repo: str, pr_number: int) -> str:
            raise AssertionError("should not approve merged PR")

        def merge_pr(self, repo: str, pr_number: int) -> str:
            raise AssertionError("should not merge merged PR")

    monkeypatch.setattr(nodes, "GitHubClient", FakeClient)
    monkeypatch.setenv("ALLOW_WRITE_ACTIONS", "true")
    monkeypatch.setenv("SANDBOX_REPO", "dwgupta/migration-sandbox-capstone")
    from pr_governance_agent.config import get_settings

    get_settings.cache_clear()

    state = initial_state(
        pr_url="https://github.com/dwgupta/migration-sandbox-capstone/pull/1",
        mode="auto",
        repo="dwgupta/migration-sandbox-capstone",
        pr_number=1,
    )
    state["passed"] = True
    state["pr_metadata"] = {
        "title": "Already merged",
        "merged": True,
        "merged_at": "2026-06-01T12:00:00Z",
        "state": "closed",
    }
    state["github_actions_taken"] = ["advisory_review_generated"]

    result = nodes.execute_github_auto(state)
    actions = result.get("github_actions_taken") or []
    assert "auto_skipped_already_merged" in actions
    assert "approved" not in actions
    assert "merged" not in actions
    assert nodes.ALREADY_MERGED_WARNING in (result.get("warnings") or [])


def test_ingest_pr_warns_on_merged_pr_in_auto_mode(monkeypatch):
    from pr_governance_agent.graph import nodes
    from pr_governance_agent.state import initial_state

    def fake_fetch(self, pr_url: str):
        return {
            "pr_url": pr_url,
            "repo": "dwgupta/migration-sandbox-capstone",
            "pr_number": 1,
            "pr_metadata": {
                "title": "Merged PR",
                "merged": True,
                "merged_at": "2026-06-01T12:00:00Z",
                "state": "closed",
            },
            "changed_files": [],
            "patches": [],
            "ci_status": None,
        }

    monkeypatch.setattr(
        "pr_governance_agent.graph.nodes.GitHubClient.fetch_pr",
        fake_fetch,
    )

    state = initial_state(
        pr_url="https://github.com/dwgupta/migration-sandbox-capstone/pull/1",
        mode="auto",
    )
    result = nodes.ingest_pr(state)
    assert nodes.ALREADY_MERGED_WARNING in (result.get("warnings") or [])
