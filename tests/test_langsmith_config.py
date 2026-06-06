"""LangSmith env bootstrap from Settings."""

import os

from pr_governance_agent.config import Settings, apply_langsmith_env, get_settings


def test_apply_langsmith_env_sets_tracing(restore_os_environ):
    """apply_langsmith_env must export tracing vars without leaking fake keys."""
    os.environ.pop("LANGSMITH_TRACING", None)
    os.environ.pop("LANGCHAIN_TRACING_V2", None)

    settings = Settings.model_construct(
        langsmith_tracing=True,
        langsmith_api_key="lsv2_pt_test",
        langsmith_project="test-project",
    )
    apply_langsmith_env(settings)

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "lsv2_pt_test"
    assert os.environ["LANGSMITH_PROJECT"] == "test-project"


def test_get_settings_cached():
    get_settings.cache_clear()
    a = get_settings()
    b = get_settings()
    assert a is b
