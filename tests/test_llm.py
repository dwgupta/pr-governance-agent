"""Tests for LLM evaluation and fallback warnings."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pr_governance_agent.graph.llm import (
    FALLBACK_WARNING_PREFIX,
    _parse_findings_json,
    evaluate_with_llm_or_heuristic,
)
from pr_governance_agent.state import PRReviewState, RetrievalChunk


def _state(**overrides) -> PRReviewState:
    base: PRReviewState = {
        "patches": [],
        "pr_metadata": {},
        "warnings": [],
        "token_usage": {},
    }
    base.update(overrides)
    return base


def test_parse_findings_json_strips_markdown_fence():
    text = '```json\n[{"severity":"high","category":"x","message":"m","file":"f","citation":"c"}]\n```'
    raw = _parse_findings_json(text)
    assert len(raw) == 1
    assert raw[0]["severity"] == "high"


@patch("pr_governance_agent.graph.llm._get_llm")
def test_llm_fallback_adds_warning(mock_get_llm):
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("API unavailable")
    mock_get_llm.return_value = llm

    state = _state(
        patches=[
            {
                "filename": "sql/legacy_extract.sql",
                "patch": "+SELECT * FROM payments WHERE ROWNUM <= 1000",
            }
        ]
    )
    findings = evaluate_with_llm_or_heuristic(state, "requirements", [])

    assert len(findings) >= 1
    assert any(FALLBACK_WARNING_PREFIX in w for w in state.get("warnings") or [])
    assert any("ROWNUM" in f["message"] for f in findings)


@patch("pr_governance_agent.graph.llm._get_llm")
def test_llm_success_no_fallback_warning(mock_get_llm):
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(
        content=json.dumps(
            [
                {
                    "severity": "high",
                    "category": "dialect",
                    "message": "ROWNUM is Oracle-specific",
                    "file": "sql/legacy_extract.sql",
                    "citation": "dialect_conversion_guide.md / Common replacements",
                }
            ]
        ),
        usage_metadata={"input_tokens": 512, "output_tokens": 64, "total_tokens": 576},
        response_metadata={},
    )
    mock_get_llm.return_value = llm

    state = _state(
        patches=[
            {
                "filename": "sql/legacy_extract.sql",
                "patch": "+SELECT * FROM payments WHERE ROWNUM <= 1000",
            }
        ]
    )
    chunk: RetrievalChunk = {
        "id": "1",
        "text": "Replace ROWNUM with ROW_NUMBER()",
        "source": "dialect_conversion_guide.md",
        "section": "Common replacements",
        "score": 0.9,
    }
    findings = evaluate_with_llm_or_heuristic(state, "requirements", [chunk])

    assert len(findings) == 1
    assert not any(FALLBACK_WARNING_PREFIX in w for w in state.get("warnings") or [])
    usage = state.get("token_usage", {}).get("requirements") or {}
    assert usage.get("calls") == 1
    assert usage.get("input_tokens") == 512
    assert usage.get("output_tokens") == 64


@patch("pr_governance_agent.graph.llm._get_llm")
def test_heuristic_mode_no_fallback_warning_when_llm_disabled(mock_get_llm):
    mock_get_llm.return_value = None

    state = _state(
        patches=[
            {
                "filename": "sql/legacy_extract.sql",
                "patch": "+SELECT * FROM payments WHERE ROWNUM <= 1000",
            }
        ]
    )
    findings = evaluate_with_llm_or_heuristic(state, "requirements", [])

    assert findings
    assert not state.get("warnings")
