"""Tests for section-first markdown chunking and table preservation.

Verifies ingest_markdown splits on ## headings and keeps dialect tables intact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pr_governance_agent.rag.ingest_markdown import (
    _chunk_section,
    _split_sections,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "sample_corpus"


def test_split_sections_extracts_h1_and_headings():
    content = (CORPUS / "bigquery_migration_requirements.md").read_text(encoding="utf-8")
    doc_title, sections = _split_sections(content)
    assert doc_title == "BigQuery Migration Engineering Requirements"
    assert len(sections) == 5
    assert sections[0][0] == "Partitioning and clustering"


def test_section_chunks_include_h1_prefix():
    content = (CORPUS / "security_pii_policy.md").read_text(encoding="utf-8")
    doc_title, sections = _split_sections(content)
    section_title, body = sections[0]
    chunks = _chunk_section(section_title, body, doc_title, "security_pii_policy.md")
    assert len(chunks) == 1
    _, payload = chunks[0]
    assert payload["text"].startswith("Data Security and PII Policy > Prohibited raw fields")
    assert payload["metadata"]["doc_title"] == "Data Security and PII Policy"


def test_table_section_stays_atomic():
    content = (CORPUS / "dialect_conversion_guide.md").read_text(encoding="utf-8")
    doc_title, sections = _split_sections(content)
    section_title, body = sections[0]
    assert "ROWNUM" in body
    chunks = _chunk_section(section_title, body, doc_title, "dialect_conversion_guide.md")
    assert len(chunks) == 1
    assert "| Oracle | BigQuery |" in chunks[0][1]["text"]


def test_oversized_section_triggers_token_fallback():
    long_body = "word " * 700
    chunks = _chunk_section("Long section", long_body, "Test Doc", "test.md")
    assert len(chunks) > 1
    for _, payload in chunks:
        assert payload["text"].startswith("Test Doc > Long section")


def test_sample_corpus_section_counts():
    expected = {
        "bigquery_migration_requirements.md": 5,
        "dialect_conversion_guide.md": 3,
        "security_pii_policy.md": 4,
    }
    for filename, count in expected.items():
        content = (CORPUS / filename).read_text(encoding="utf-8")
        _, sections = _split_sections(content)
        total_chunks = sum(
            len(_chunk_section(title, body, _split_sections(content)[0], filename))
            for title, body in sections
        )
        assert total_chunks == count, filename
