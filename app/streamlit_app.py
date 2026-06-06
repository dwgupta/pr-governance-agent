"""Streamlit dashboard for PR Governance Agent.

Runs the LangGraph workflow in a background thread so the UI stays responsive.
Runtime toggles in the sidebar update process env vars before each run (no .env edit).
"""

from __future__ import annotations

import os

# Avoid Streamlit probing transformers vision modules (requires torchvision).
os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")

import sys
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pr_governance_agent.config import apply_langsmith_env, get_settings
from pr_governance_agent.graph.builder import compile_graph
from pr_governance_agent.state import initial_state

st.set_page_config(page_title="PR Governance Agent", layout="wide")
st.title("PR Governance Agent")
st.caption("Agentic PR review for data engineering migration workflows (RAG + GitHub + optional SAST)")

# Session state: single-thread executor avoids blocking the Streamlit event loop
if "executor" not in st.session_state:
    st.session_state.executor = ThreadPoolExecutor(max_workers=1)
if "future" not in st.session_state:
    st.session_state.future = None
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "run_error" not in st.session_state:
    st.session_state.run_error = None

# How often Streamlit reruns while waiting for the background graph job.
_RUN_POLL_SECONDS = 1.0


def _env_bool(value: bool) -> str:
    return "true" if value else "false"


def _apply_runtime_config(config: dict[str, Any]) -> None:
    """Push sidebar values into os.environ and reload cached Settings."""
    env_map = {
        "USE_PR_FIXTURE": _env_bool(config["use_pr_fixture"]),
        "HEURISTIC_ONLY": _env_bool(config["heuristic_only"]),
        "ALLOW_WRITE_ACTIONS": _env_bool(config["allow_write_actions"]),
        "POST_PR_COMMENTS": _env_bool(config["post_pr_comments"]),
        "ENABLE_SAST": _env_bool(config["enable_sast"]),
        "LANGSMITH_TRACING": _env_bool(config["langsmith_tracing"]),
        "SANDBOX_REPO": config["sandbox_repo"].strip(),
    }
    for key, value in env_map.items():
        os.environ[key] = value

    fixture_path = config.get("pr_fixture_path", "").strip()
    if fixture_path:
        os.environ["PR_FIXTURE_PATH"] = fixture_path
    else:
        os.environ.pop("PR_FIXTURE_PATH", None)

    # Empty fields keep existing .env values (do not wipe secrets).
    if config.get("github_token", "").strip():
        os.environ["GITHUB_TOKEN"] = config["github_token"].strip()
    if config.get("openai_api_key", "").strip():
        os.environ["OPENAI_API_KEY"] = config["openai_api_key"].strip()

    get_settings.cache_clear()
    apply_langsmith_env(get_settings())


def _run_graph(pr_url: str, mode: str, runtime_config: dict[str, Any]) -> dict:
    """Invoke compiled graph; each run gets a unique thread_id for checkpointing."""
    _apply_runtime_config(runtime_config)
    app = compile_graph()
    state = initial_state(pr_url=pr_url, mode=mode)
    return app.invoke(state, config={"configurable": {"thread_id": str(uuid.uuid4())}})


def _init_defaults() -> None:
    """Seed session_state widget defaults from .env once per browser session."""
    if st.session_state.get("_defaults_loaded"):
        return
    base = get_settings()
    st.session_state.setdefault("use_pr_fixture", base.use_pr_fixture)
    st.session_state.setdefault("heuristic_only", base.heuristic_only)
    st.session_state.setdefault("allow_write_actions", base.allow_write_actions)
    st.session_state.setdefault("post_pr_comments", base.post_pr_comments)
    st.session_state.setdefault("enable_sast", base.enable_sast)
    st.session_state.setdefault("langsmith_tracing", base.langsmith_tracing)
    st.session_state.setdefault("sandbox_repo", base.sandbox_repo or "dwgupta/migration-sandbox-capstone")
    st.session_state.setdefault("pr_fixture_path", os.environ.get("PR_FIXTURE_PATH", ""))
    st.session_state["_defaults_loaded"] = True


_init_defaults()

with st.sidebar:
    st.header("Runtime settings")
    st.caption("Changes apply on the next **Run review** (no app restart).")

    use_pr_fixture = st.toggle(
        "Use PR fixture (offline)",
        key="use_pr_fixture",
        help="Load PR data from local JSON instead of GitHub API.",
    )
    heuristic_only = st.toggle(
        "Heuristic only (no LLM)",
        key="heuristic_only",
        help="Skip OpenAI; use regex-based checks only.",
    )
    allow_write_actions = st.toggle(
        "Allow write actions",
        key="allow_write_actions",
        help="Required for auto approve/merge in auto mode.",
    )
    post_pr_comments = st.toggle(
        "Post PR comments",
        key="post_pr_comments",
        help="Post review markdown as a GitHub PR comment when token is set.",
    )
    enable_sast = st.toggle(
        "Enable SAST (Semgrep)",
        key="enable_sast",
        help="Run Semgrep on patches if semgrep is installed.",
    )
    langsmith_tracing = st.toggle(
        "LangSmith tracing",
        key="langsmith_tracing",
        help="Requires LANGSMITH_API_KEY in .env.",
    )

    sandbox_repo = st.text_input(
        "Sandbox repo (owner/name)",
        key="sandbox_repo",
        help="Repo allowed for auto approve/merge.",
    )
    pr_fixture_path = st.text_input(
        "PR fixture path (optional)",
        key="pr_fixture_path",
        placeholder="docs/samples/success_pr_fixture.json",
        help="Override default eval/fixtures/sample_pr.json when offline.",
    )

    with st.expander("Optional API key override"):
        st.caption("Leave blank to keep values from `.env`.")
        github_token_override = st.text_input(
            "GitHub token override",
            type="password",
            key="github_token_override",
        )
        openai_api_key_override = st.text_input(
            "OpenAI API key override",
            type="password",
            key="openai_api_key_override",
        )

    runtime_config = {
        "use_pr_fixture": use_pr_fixture,
        "heuristic_only": heuristic_only,
        "allow_write_actions": allow_write_actions,
        "post_pr_comments": post_pr_comments,
        "enable_sast": enable_sast,
        "langsmith_tracing": langsmith_tracing,
        "sandbox_repo": sandbox_repo,
        "pr_fixture_path": pr_fixture_path,
        "github_token": github_token_override,
        "openai_api_key": openai_api_key_override,
    }
    _apply_runtime_config(runtime_config)
    settings = get_settings()

    st.divider()
    st.header("Effective status")
    st.write(f"LLM enabled: **{settings.llm_enabled}**")
    if settings.langsmith_enabled:
        st.write(
            f"LangSmith tracing: **on** (`{settings.langsmith_project}`) — "
            "[dashboard](https://smith.langchain.com)"
        )
    else:
        st.write("LangSmith tracing: **off**")
    st.write(f"Offline fixture mode: **{settings.use_pr_fixture}**")
    st.write(f"Write actions allowed: **{settings.allow_write_actions}**")
    if settings.sandbox_repo:
        st.write(f"Sandbox repo: `{settings.sandbox_repo}`")

    from pr_governance_agent.rag.chroma_store import ChromaStore

    rag_warnings = ChromaStore().rag_index_warnings()
    if rag_warnings:
        for warning in rag_warnings:
            st.warning(warning)

pr_url = st.text_input(
    "GitHub PR URL",
    value="https://github.com/dwgupta/migration-sandbox-capstone/pull/1",
    help="Used with GITHUB_TOKEN, or ignored when offline fixture mode is on.",
)

mode = st.radio(
    "Mode",
    options=["advisory", "auto"],
    index=0,
    horizontal=True,
    help="Advisory: generate review only. Auto: approve/merge only if writes are allowed and sandbox matches.",
)

if mode == "auto" and not st.session_state.get("allow_write_actions"):
    st.warning(
        "Auto mode is selected but **Allow write actions** is off in the sidebar. "
        "No approve/merge will occur."
    )

col1, col2 = st.columns(2)
with col1:
    run_clicked = st.button("Run review", type="primary")
with col2:
    if st.button("Clear results"):
        st.session_state.last_result = None
        st.session_state.future = None
        st.session_state.run_error = None

if run_clicked:
    run_config = {
        "use_pr_fixture": st.session_state.use_pr_fixture,
        "heuristic_only": st.session_state.heuristic_only,
        "allow_write_actions": st.session_state.allow_write_actions,
        "post_pr_comments": st.session_state.post_pr_comments,
        "enable_sast": st.session_state.enable_sast,
        "langsmith_tracing": st.session_state.langsmith_tracing,
        "sandbox_repo": st.session_state.sandbox_repo,
        "pr_fixture_path": st.session_state.pr_fixture_path,
        "github_token": st.session_state.get("github_token_override", ""),
        "openai_api_key": st.session_state.get("openai_api_key_override", ""),
    }
    st.session_state.last_result = None
    st.session_state.run_error = None
    st.session_state.future = st.session_state.executor.submit(
        _run_graph, pr_url, mode, run_config
    )
    st.rerun()

if st.session_state.future is not None:
    future: Future = st.session_state.future
    if future.done():
        try:
            st.session_state.last_result = future.result()
        except Exception as exc:
            st.session_state.run_error = str(exc)
        st.session_state.future = None
        st.rerun()
    else:
        with st.status("Agent running…", state="running"):
            st.caption(
                "PR governance workflow is running in the background. "
                "This page refreshes automatically every second."
            )
        time.sleep(_RUN_POLL_SECONDS)
        st.rerun()

if st.session_state.run_error:
    st.error(f"Run failed: {st.session_state.run_error}")

result = st.session_state.last_result
if result:
    risk = result.get("overall_risk", "unknown")
    passed = result.get("passed", False)
    st.metric("Overall risk", risk)
    st.metric("Passed", "Yes" if passed else "No")

    if result.get("blockers"):
        st.error("Blockers:\n" + "\n".join(f"- {b}" for b in result["blockers"]))

    for warning in result.get("warnings") or []:
        st.warning(warning)

    with st.expander("GitHub actions taken"):
        for action in result.get("github_actions_taken") or []:
            st.write(f"- {action}")

    with st.expander("Node timings (seconds)"):
        st.json(result.get("node_timings") or {})

    st.subheader("Review")
    st.markdown(result.get("review_markdown") or "_No review generated._")

    with st.expander("Raw state"):
        st.json({k: v for k, v in result.items() if k != "review_markdown"})
