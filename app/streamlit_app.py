"""Streamlit dashboard for PR Governance Agent."""

from __future__ import annotations

import sys
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pr_governance_agent.config import get_settings
from pr_governance_agent.graph.builder import compile_graph
from pr_governance_agent.state import initial_state

st.set_page_config(page_title="PR Governance Agent", layout="wide")
st.title("PR Governance Agent")
st.caption("Agentic PR review for data engineering migration workflows (RAG + GitHub + optional SAST)")

settings = get_settings()

if "executor" not in st.session_state:
    st.session_state.executor = ThreadPoolExecutor(max_workers=1)
if "future" not in st.session_state:
    st.session_state.future = None
if "last_result" not in st.session_state:
    st.session_state.last_result = None


def _run_graph(pr_url: str, mode: str) -> dict:
    app = compile_graph()
    state = initial_state(pr_url=pr_url, mode=mode)
    return app.invoke(state, config={"configurable": {"thread_id": str(uuid.uuid4())}})


with st.sidebar:
    st.header("Settings")
    st.write(f"LLM enabled: **{settings.llm_enabled}**")
    st.write(f"Write actions allowed: **{settings.allow_write_actions}**")
    if settings.sandbox_repo:
        st.write(f"Sandbox repo: `{settings.sandbox_repo}`")
    st.info("Set `USE_PR_FIXTURE=true` for offline demo without GitHub token.")

pr_url = st.text_input(
    "GitHub PR URL",
    value="https://github.com/demo/migration-sandbox/pull/1",
    help="Used with GITHUB_TOKEN, or ignored when USE_PR_FIXTURE=true",
)

mode = st.radio(
    "Mode",
    options=["advisory", "auto"],
    index=0,
    horizontal=True,
    help="Advisory: generate review only. Auto: approve/merge only if ALLOW_WRITE_ACTIONS and SANDBOX_REPO match.",
)

if mode == "auto" and not settings.allow_write_actions:
    st.warning(
        "Auto mode is selected but `ALLOW_WRITE_ACTIONS` is false. "
        "No approve/merge will occur."
    )

col1, col2 = st.columns(2)
with col1:
    run_clicked = st.button("Run review", type="primary")
with col2:
    if st.button("Clear results"):
        st.session_state.last_result = None
        st.session_state.future = None

if run_clicked:
    with st.spinner("Running LangGraph workflow..."):
        st.session_state.future = st.session_state.executor.submit(_run_graph, pr_url, mode)

if st.session_state.future is not None:
    future: Future = st.session_state.future
    if future.done():
        try:
            st.session_state.last_result = future.result()
        except Exception as exc:
            st.error(f"Run failed: {exc}")
        st.session_state.future = None
    else:
        st.status("Agent running…", state="running")

result = st.session_state.last_result
if result:
    risk = result.get("overall_risk", "unknown")
    passed = result.get("passed", False)
    st.metric("Overall risk", risk)
    st.metric("Passed", "Yes" if passed else "No")

    if result.get("blockers"):
        st.error("Blockers:\n" + "\n".join(f"- {b}" for b in result["blockers"]))

    with st.expander("GitHub actions taken"):
        for action in result.get("github_actions_taken") or []:
            st.write(f"- {action}")

    with st.expander("Node timings (seconds)"):
        st.json(result.get("node_timings") or {})

    st.subheader("Review")
    st.markdown(result.get("review_markdown") or "_No review generated._")

    with st.expander("Raw state"):
        st.json({k: v for k, v in result.items() if k != "review_markdown"})
