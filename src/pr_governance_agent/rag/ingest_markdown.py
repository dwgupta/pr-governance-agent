import hashlib
import re
from pathlib import Path

from pr_governance_agent.rag.chroma_store import (
    REQUIREMENTS_COLLECTION,
    SECURITY_COLLECTION,
    ChromaStore,
)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def _chunk_text(text: str, source: str, section: str) -> list[tuple[str, dict]]:
    words = text.split()
    if not words:
        return []

    chunks: list[tuple[str, dict]] = []
    step = max(CHUNK_SIZE - CHUNK_OVERLAP, 1)
    for i in range(0, len(words), step):
        piece = " ".join(words[i : i + CHUNK_SIZE])
        if not piece.strip():
            continue
        chunk_id = hashlib.sha256(f"{source}:{section}:{i}".encode()).hexdigest()[:16]
        chunks.append(
            (
                chunk_id,
                {
                    "text": piece,
                    "metadata": {"source": source, "section": section},
                },
            )
        )
    return chunks


def _split_sections(content: str) -> list[tuple[str, str]]:
    parts = re.split(r"^(## .+)$", content, flags=re.MULTILINE)
    if len(parts) <= 1:
        return [("body", content.strip())]

    sections: list[tuple[str, str]] = []
    i = 1
    while i < len(parts):
        title = parts[i].strip("# ").strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((title, body.strip()))
        i += 2
    return sections


def ingest_markdown_file(
    path: Path,
    collection_name: str,
    store: ChromaStore | None = None,
) -> int:
    store = store or ChromaStore()
    collection = store.get_or_create_collection(collection_name)
    content = path.read_text(encoding="utf-8")
    source = path.name
    total = 0

    for section, body in _split_sections(content):
        for chunk_id, payload in _chunk_text(body, source, section):
            collection.upsert(
                ids=[chunk_id],
                documents=[payload["text"]],
                metadatas=[payload["metadata"]],
            )
            total += 1
    return total


def ingest_corpus_dir(
    corpus_dir: Path,
    store: ChromaStore | None = None,
) -> dict[str, int]:
    store = store or ChromaStore()
    counts = {REQUIREMENTS_COLLECTION: 0, SECURITY_COLLECTION: 0}

    for path in sorted(corpus_dir.glob("*.md")):
        name_lower = path.name.lower()
        if "security" in name_lower or "pii" in name_lower:
            coll = SECURITY_COLLECTION
        else:
            coll = REQUIREMENTS_COLLECTION
        counts[coll] += ingest_markdown_file(path, coll, store)

    return counts
