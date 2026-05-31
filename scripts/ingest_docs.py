#!/usr/bin/env python3
"""Ingest sample corpus (and optional PDFs) into ChromaDB."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pr_governance_agent.rag.chroma_store import (
    REQUIREMENTS_COLLECTION,
    SECURITY_COLLECTION,
)
from pr_governance_agent.rag.ingest_markdown import ingest_corpus_dir
from pr_governance_agent.rag.ingest_pdf import ingest_pdf_file


def main() -> int:
    corpus_dir = ROOT / "data" / "sample_corpus"
    if not corpus_dir.exists():
        print(f"Missing corpus directory: {corpus_dir}", file=sys.stderr)
        return 1

    counts = ingest_corpus_dir(corpus_dir)
    print(f"Ingested markdown -> requirements: {counts[REQUIREMENTS_COLLECTION]}")
    print(f"Ingested markdown -> security: {counts[SECURITY_COLLECTION]}")

    for pdf in corpus_dir.glob("*.pdf"):
        coll = (
            SECURITY_COLLECTION
            if "security" in pdf.name.lower()
            else REQUIREMENTS_COLLECTION
        )
        n = ingest_pdf_file(pdf, coll)
        print(f"Ingested {pdf.name} -> {coll}: {n} chunks")

    manifest = {
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "corpus_dir": str(corpus_dir),
        "collections": {
            REQUIREMENTS_COLLECTION: counts[REQUIREMENTS_COLLECTION],
            SECURITY_COLLECTION: counts[SECURITY_COLLECTION],
        },
        "sources": sorted(p.name for p in corpus_dir.glob("*") if p.is_file()),
    }
    manifest_path = ROOT / "data" / "index_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {manifest_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
