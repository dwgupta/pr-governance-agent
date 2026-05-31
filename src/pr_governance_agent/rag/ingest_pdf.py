import re
from pathlib import Path

from pypdf import PdfReader

from pr_governance_agent.rag.chroma_store import ChromaStore
from pr_governance_agent.rag.ingest_markdown import _chunk_section, _extract_h1

_HEADING_PATTERN = re.compile(
    r"^(?:#{1,3}\s+.+|[A-Z][A-Z0-9\s\-]{3,})$",
    re.MULTILINE,
)


def _split_pdf_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    doc_title = _extract_h1(text)
    if not _HEADING_PATTERN.search(text):
        return doc_title, [("pdf", text.strip())]

    parts = re.split(r"^((?:#{1,3}\s+.+|[A-Z][A-Z0-9\s\-]{3,}))$", text, flags=re.MULTILINE)
    if len(parts) <= 1:
        return doc_title, [("pdf", text.strip())]

    sections: list[tuple[str, str]] = []
    i = 1
    while i < len(parts):
        raw_title = parts[i].strip().lstrip("#").strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((raw_title or "pdf", body.strip()))
        i += 2
    return doc_title, sections


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

    doc_title = path.stem.replace("_", " ").replace("-", " ")
    if not doc_title:
        doc_title = path.name

    _, sections = _split_pdf_sections(text)
    for section_title, body in sections:
        for chunk_id, payload in _chunk_section(
            section_title, body, doc_title, path.name
        ):
            collection.upsert(
                ids=[chunk_id],
                documents=[payload["text"]],
                metadatas=[payload["metadata"]],
            )
            total += 1
    return total
