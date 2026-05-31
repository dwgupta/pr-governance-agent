from pathlib import Path

from pypdf import PdfReader

from pr_governance_agent.rag.ingest_markdown import _chunk_text
from pr_governance_agent.rag.chroma_store import ChromaStore


def ingest_pdf_file(
    path: Path,
    collection_name: str,
    store: ChromaStore | None = None,
) -> int:
    store = store or ChromaStore()
    collection = store.get_or_create_collection(collection_name)
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    total = 0
    for chunk_id, payload in _chunk_text(text, path.name, "pdf"):
        collection.upsert(
            ids=[chunk_id],
            documents=[payload["text"]],
            metadatas=[payload["metadata"]],
        )
        total += 1
    return total
