from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from pr_governance_agent.config import get_settings
from pr_governance_agent.rag.reranker import rerank as rerank_chunks
from pr_governance_agent.state import RetrievalChunk

REQUIREMENTS_COLLECTION = "requirements"
SECURITY_COLLECTION = "security_policies"

HNSW_SPACE = "cosine"
HNSW_CONSTRUCTION_EF = 100
HNSW_SEARCH_EF = 50


class ChromaStore:
    def __init__(self, persist_dir: Path | None = None) -> None:
        settings = get_settings()
        path = persist_dir or settings.chroma_persist_dir
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def get_or_create_collection(self, name: str):
        return self._client.get_or_create_collection(
            name=name,
            metadata={
                "hnsw:space": HNSW_SPACE,
                "hnsw:construction_ef": HNSW_CONSTRUCTION_EF,
                "hnsw:search_ef": HNSW_SEARCH_EF,
            },
        )

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
    ) -> list[RetrievalChunk]:
        collection = self.get_or_create_collection(collection_name)
        if collection.count() == 0:
            return []

        result = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, max(collection.count(), 1)),
        )

        chunks: list[RetrievalChunk] = []
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else 1.0
            score = max(0.0, 1.0 - dist)
            chunk: RetrievalChunk = {
                "id": doc_id,
                "text": docs[i] if i < len(docs) else "",
                "source": str(meta.get("source", "unknown")),
                "section": str(meta.get("section", "")),
                "score": score,
            }
            doc_title = meta.get("doc_title")
            if doc_title:
                chunk["doc_title"] = str(doc_title)
            chunks.append(chunk)
        return chunks

    def retrieve(
        self,
        collection_name: str,
        query_text: str,
        retrieve_n: int | None = None,
        top_k: int | None = None,
        enable_rerank: bool | None = None,
    ) -> list[RetrievalChunk]:
        settings = get_settings()
        wide_n = retrieve_n if retrieve_n is not None else settings.rag_retrieve_n
        final_k = top_k if top_k is not None else settings.rag_top_k
        use_rerank = enable_rerank if enable_rerank is not None else settings.rag_rerank_enabled

        candidates = self.query(collection_name, query_text, n_results=wide_n)
        if not candidates:
            return []

        if use_rerank:
            return rerank_chunks(query_text, candidates, top_k=final_k)

        return candidates[: max(1, final_k)]

    def collection_count(self, collection_name: str) -> int:
        return self.get_or_create_collection(collection_name).count()

    def rag_index_warnings(self) -> list[str]:
        """Return warnings when policy collections have not been ingested."""
        warnings: list[str] = []
        for collection_name, label in (
            (REQUIREMENTS_COLLECTION, "requirements"),
            (SECURITY_COLLECTION, "security policies"),
        ):
            if self.collection_count(collection_name) == 0:
                warnings.append(
                    f"Chroma '{label}' index is empty — policy citations are disabled. "
                    "Run: python scripts/ingest_docs.py"
                )
        return warnings
