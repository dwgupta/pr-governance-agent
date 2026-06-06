"""LLM token usage aggregation and estimated cost helpers."""

from __future__ import annotations

from typing import Any

from pr_governance_agent.config import Settings
from pr_governance_agent.state import LLMCallUsage

# USD per 1M tokens — override via OPENAI_INPUT_COST_PER_1M / OPENAI_OUTPUT_COST_PER_1M.
_DEFAULT_INPUT_COST_PER_1M = 0.15
_DEFAULT_OUTPUT_COST_PER_1M = 0.60


def empty_llm_usage() -> LLMCallUsage:
    """Return a zeroed usage record for one evaluation step."""
    return LLMCallUsage(calls=0, input_tokens=0, output_tokens=0, total_tokens=0)


def extract_tokens_from_response(resp: Any) -> tuple[int, int, int]:
    """Read input/output/total token counts from a LangChain chat response."""
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0

    usage_metadata = getattr(resp, "usage_metadata", None)
    if usage_metadata:
        input_tokens = int(usage_metadata.get("input_tokens") or 0)
        output_tokens = int(usage_metadata.get("output_tokens") or 0)
        total_tokens = int(usage_metadata.get("total_tokens") or 0)

    if not total_tokens and hasattr(resp, "response_metadata"):
        token_usage = (getattr(resp, "response_metadata", None) or {}).get("token_usage") or {}
        if token_usage:
            input_tokens = int(
                token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or input_tokens
            )
            output_tokens = int(
                token_usage.get("completion_tokens")
                or token_usage.get("output_tokens")
                or output_tokens
            )
            total_tokens = int(token_usage.get("total_tokens") or 0)

    if not total_tokens:
        total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def normalize_usage_entry(value: Any) -> LLMCallUsage:
    """Coerce legacy call-count ints or partial dicts into ``LLMCallUsage``."""
    if isinstance(value, int):
        return LLMCallUsage(
            calls=value,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
        )
    if isinstance(value, dict):
        return LLMCallUsage(
            calls=int(value.get("calls") or 0),
            input_tokens=int(value.get("input_tokens") or 0),
            output_tokens=int(value.get("output_tokens") or 0),
            total_tokens=int(value.get("total_tokens") or 0),
        )
    return empty_llm_usage()


def record_llm_call(state: dict[str, Any], kind: str, resp: Any) -> None:
    """Append one LLM invocation's token counts to ``state["token_usage"][kind]``."""
    usage = dict(state.get("token_usage") or {})
    entry = normalize_usage_entry(usage.get(kind))
    input_tokens, output_tokens, total_tokens = extract_tokens_from_response(resp)

    entry["calls"] += 1
    entry["input_tokens"] += input_tokens
    entry["output_tokens"] += output_tokens
    entry["total_tokens"] += total_tokens
    usage[kind] = entry
    state["token_usage"] = usage


def aggregate_token_usage(token_usage: dict[str, Any] | None) -> LLMCallUsage:
    """Sum per-step usage (requirements, security, etc.) into one total."""
    totals = empty_llm_usage()
    for value in (token_usage or {}).values():
        entry = normalize_usage_entry(value)
        totals["calls"] += entry["calls"]
        totals["input_tokens"] += entry["input_tokens"]
        totals["output_tokens"] += entry["output_tokens"]
        totals["total_tokens"] += entry["total_tokens"]
    return totals


def estimate_llm_cost(
    input_tokens: int,
    output_tokens: int,
    settings: Settings,
) -> float:
    """Estimate USD cost from token counts and configured per-1M rates."""
    input_rate = settings.openai_input_cost_per_1m
    output_rate = settings.openai_output_cost_per_1m
    return (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)


def format_usd(amount: float) -> str:
    """Human-readable USD string for small LLM run costs."""
    if amount >= 0.01:
        return f"${amount:.4f}"
    if amount > 0:
        return f"${amount:.6f}"
    return "$0.00"
