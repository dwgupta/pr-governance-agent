"""Cross-encoder reranking for RAG retrieval precision.

After HNSW returns N candidates, a sentence-transformers CrossEncoder scores
each (query, chunk) pair and returns the top-k by relevance score.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pr_governance_agent.config import get_settings
from pr_governance_agent.state import RetrievalChunk

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_cross_encoder(model_name: str):
    """Load reranker once per process (downloads from Hugging Face on first use)."""
    # Ensure HF_TOKEN from .env is exported to os.environ before Hub download.
    get_settings()
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name)


def rerank(
    query: str,
    chunks: list[RetrievalChunk],
    top_k: int,
    model_name: str | None = None,
) -> list[RetrievalChunk]:
    """Reorder chunks by cross-encoder score; preserve original score as vector_score."""
    if not chunks:
        return []

    settings = get_settings()
    model = model_name or settings.rag_rerank_model
    limit = max(1, min(top_k, len(chunks)))

    try:
        encoder = _load_cross_encoder(model)
        pairs = [(query, chunk["text"]) for chunk in chunks]
        scores = encoder.predict(pairs)
    except Exception as exc:
        logger.warning("Reranker unavailable (%s); using vector order", exc)
        return chunks[:limit]

    ranked: list[RetrievalChunk] = []
    for chunk, score in sorted(
        zip(chunks, scores, strict=True),
        key=lambda item: float(item[1]),
        reverse=True,
    ):
        reranked = dict(chunk)
        reranked["vector_score"] = chunk["score"]
        reranked["score"] = float(score)
        ranked.append(reranked)  # type: ignore[arg-type]

    return ranked[:limit]
