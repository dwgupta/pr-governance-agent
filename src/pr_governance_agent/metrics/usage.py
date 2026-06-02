"""Lightweight per-node timing for graph observability."""

import time
from contextlib import contextmanager
from typing import Generator

from pr_governance_agent.state import PRReviewState


@contextmanager
def track_node(state: PRReviewState, node_name: str) -> Generator[None, None, None]:
    """Record elapsed seconds for ``node_name`` in ``state['node_timings']``."""
    start = time.perf_counter()
    try:
        yield
    finally:
        timings = dict(state.get("node_timings") or {})
        timings[node_name] = round(time.perf_counter() - start, 3)
        state["node_timings"] = timings
