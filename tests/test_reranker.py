"""Tests for cross-encoder reranking."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pr_governance_agent.rag.reranker import rerank
from pr_governance_agent.state import RetrievalChunk


def _chunk(chunk_id: str, text: str, score: float) -> RetrievalChunk:
    return {
        "id": chunk_id,
        "text": text,
        "source": "test.md",
        "section": "body",
        "score": score,
    }


@patch("pr_governance_agent.rag.reranker._load_cross_encoder")
def test_rerank_reorders_by_cross_encoder_score(mock_load):
    encoder = MagicMock()
    encoder.predict.return_value = [0.2, 0.9, 0.5]
    mock_load.return_value = encoder

    chunks = [
        _chunk("a", "partition filter", 0.8),
        _chunk("b", "ROWNUM Oracle dialect", 0.7),
        _chunk("c", "dbt schema tests", 0.6),
    ]
    result = rerank("ROWNUM Oracle dialect", chunks, top_k=2)

    assert len(result) == 2
    assert result[0]["id"] == "b"
    assert result[0]["vector_score"] == 0.7
    assert result[0]["score"] == 0.9


@patch("pr_governance_agent.rag.reranker._load_cross_encoder")
def test_rerank_falls_back_on_model_error(mock_load):
    mock_load.side_effect = RuntimeError("model unavailable")

    chunks = [
        _chunk("a", "first", 0.9),
        _chunk("b", "second", 0.5),
    ]
    result = rerank("query", chunks, top_k=1)
    assert len(result) == 1
    assert result[0]["id"] == "a"
