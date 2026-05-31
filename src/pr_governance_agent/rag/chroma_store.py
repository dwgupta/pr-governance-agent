from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from pr_governance_agent.config import get_settings
from pr_governance_agent.state import RetrievalChunk

REQUIREMENTS_COLLECTION = "requirements"
SECURITY_COLLECTION = "security_policies"


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
            metadata={"hnsw:space": "cosine"},
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
            chunks.append(
                RetrievalChunk(
                    id=doc_id,
                    text=docs[i] if i < len(docs) else "",
                    source=str(meta.get("source", "unknown")),
                    section=str(meta.get("section", "")),
                    score=score,
                )
            )
        return chunks
