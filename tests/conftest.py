"""Pytest hooks shared across the test suite."""

from __future__ import annotations

import os

import pytest

from pr_governance_agent.config import get_settings


@pytest.fixture(autouse=True)
def _disable_langsmith_tracing_during_tests(request, monkeypatch):
    """Keep LangSmith off in tests unless a test explicitly manages env itself."""
    if request.node.name == "test_apply_langsmith_env_sets_tracing":
        yield
        get_settings.cache_clear()
        return

    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def restore_os_environ():
    """Snapshot and restore ``os.environ`` for tests that mutate it directly."""
    snapshot = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(snapshot)
    get_settings.cache_clear()
