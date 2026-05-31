import hashlib
import re
from functools import lru_cache
from pathlib import Path

import tiktoken

from pr_governance_agent.rag.chroma_store import (
    REQUIREMENTS_COLLECTION,
    SECURITY_COLLECTION,
    ChromaStore,
)

# Section-first chunking: one ## section per chunk when under token limit.
MAX_SECTION_TOKENS = 512
TABLE_SECTION_MAX_TOKENS = 1024
FALLBACK_CHUNK_TOKENS = 512
FALLBACK_OVERLAP_TOKENS = 100
ENCODING_NAME = "cl100k_base"

_TABLE_PATTERN = re.compile(r"^\|.+\|", re.MULTILINE)


@lru_cache(maxsize=1)
def _tokenizer() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING_NAME)


def _count_tokens(text: str) -> int:
    if not text.strip():
        return 0
    return len(_tokenizer().encode(text))


def _contains_markdown_table(text: str) -> bool:
    return bool(_TABLE_PATTERN.search(text))


def _extract_h1(content: str) -> str:
    match = re.search(r"^# (.+)$", content, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _split_sections(content: str) -> tuple[str, list[tuple[str, str]]]:
    doc_title = _extract_h1(content)
    parts = re.split(r"^(## .+)$", content, flags=re.MULTILINE)
    if len(parts) <= 1:
        return doc_title, [("body", content.strip())]

    sections: list[tuple[str, str]] = []
    i = 1
    while i < len(parts):
        title = parts[i].strip("# ").strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((title, body.strip()))
        i += 2
    return doc_title, sections


def _format_chunk_text(doc_title: str, section_title: str, body: str) -> str:
    if doc_title and section_title:
        prefix = f"{doc_title} > {section_title}"
    elif doc_title:
        prefix = doc_title
    elif section_title:
        prefix = section_title
    else:
        prefix = ""
    if prefix:
        return f"{prefix}\n\n{body.strip()}"
    return body.strip()


def _token_window_split(text: str) -> list[str]:
    tokens = _tokenizer().encode(text)
    if not tokens:
        return []

    pieces: list[str] = []
    step = max(FALLBACK_CHUNK_TOKENS - FALLBACK_OVERLAP_TOKENS, 1)
    for start in range(0, len(tokens), step):
        window = tokens[start : start + FALLBACK_CHUNK_TOKENS]
        if not window:
            continue
        piece = _tokenizer().decode(window).strip()
        if piece:
            pieces.append(piece)
    return pieces


def _chunk_section(
    section_title: str,
    body: str,
    doc_title: str,
    source: str,
    offset_base: int = 0,
) -> list[tuple[str, dict]]:
    if not body.strip():
        return []

    has_table = _contains_markdown_table(body)
    token_limit = TABLE_SECTION_MAX_TOKENS if has_table else MAX_SECTION_TOKENS
    body_tokens = _count_tokens(body)

    if body_tokens <= token_limit:
        text = _format_chunk_text(doc_title, section_title, body)
        chunk_id = hashlib.sha256(
            f"{source}:{section_title}:{offset_base}".encode()
        ).hexdigest()[:16]
        metadata = {
            "source": source,
            "section": section_title,
            "doc_title": doc_title,
        }
        return [(chunk_id, {"text": text, "metadata": metadata})]

    chunks: list[tuple[str, dict]] = []
    for i, piece in enumerate(_token_window_split(body)):
        text = _format_chunk_text(doc_title, section_title, piece)
        offset = offset_base + i
        chunk_id = hashlib.sha256(
            f"{source}:{section_title}:{offset}".encode()
        ).hexdigest()[:16]
        metadata = {
            "source": source,
            "section": section_title,
            "doc_title": doc_title,
        }
        chunks.append((chunk_id, {"text": text, "metadata": metadata}))
    return chunks


def _chunk_text(
    text: str,
    source: str,
    section: str,
    doc_title: str = "",
) -> list[tuple[str, dict]]:
    """Backward-compatible wrapper for flat text (PDF fallback)."""
    return _chunk_section(section, text, doc_title, source)


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

    doc_title, sections = _split_sections(content)
    for section_title, body in sections:
        for chunk_id, payload in _chunk_section(
            section_title, body, doc_title, source
        ):
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
