"""Tests for LLM token usage helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pr_governance_agent.config import Settings
from pr_governance_agent.usage import (
    aggregate_token_usage,
    estimate_llm_cost,
    extract_tokens_from_response,
    normalize_usage_entry,
    record_llm_call,
)


def test_extract_tokens_from_usage_metadata():
    resp = MagicMock(
        usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
        response_metadata={},
    )
    assert extract_tokens_from_response(resp) == (120, 30, 150)


def test_extract_tokens_from_response_metadata():
    resp = MagicMock(
        usage_metadata=None,
        response_metadata={
            "token_usage": {
                "prompt_tokens": 200,
                "completion_tokens": 50,
                "total_tokens": 250,
            }
        },
    )
    assert extract_tokens_from_response(resp) == (200, 50, 250)


def test_normalize_legacy_int_usage():
    entry = normalize_usage_entry(2)
    assert entry["calls"] == 2
    assert entry["input_tokens"] == 0


def test_record_llm_call_accumulates():
    state: dict = {"token_usage": {}}
    resp = MagicMock(
        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
    )
    record_llm_call(state, "requirements", resp)
    record_llm_call(state, "requirements", resp)

    entry = state["token_usage"]["requirements"]
    assert entry["calls"] == 2
    assert entry["input_tokens"] == 200
    assert entry["output_tokens"] == 40
    assert entry["total_tokens"] == 240


def test_aggregate_token_usage():
    usage = {
        "requirements": {
            "calls": 1,
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
        },
        "security": {
            "calls": 1,
            "input_tokens": 80,
            "output_tokens": 15,
            "total_tokens": 95,
        },
    }
    totals = aggregate_token_usage(usage)
    assert totals["calls"] == 2
    assert totals["input_tokens"] == 180
    assert totals["output_tokens"] == 25


def test_estimate_llm_cost():
    settings = Settings.model_construct(
        openai_input_cost_per_1m=1.0,
        openai_output_cost_per_1m=2.0,
    )
    cost = estimate_llm_cost(1_000_000, 500_000, settings)
    assert cost == pytest.approx(2.0)
