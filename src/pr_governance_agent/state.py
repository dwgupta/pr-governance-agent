"""LangGraph state schema and factory for PR review runs.

``PRReviewState`` is the single shared dict passed through every graph node.
Fields are optional (``total=False``) because nodes populate them incrementally.
"""

from typing import Any, Literal, NotRequired, TypedDict


class RetrievalChunk(TypedDict):
    """One policy passage retrieved from Chroma (optionally reranked)."""

    id: str
    text: str
    source: str  # filename, e.g. bigquery_migration_requirements.md
    section: str  # ## heading within the doc
    score: float  # similarity or cross-encoder score
    doc_title: NotRequired[str]
    vector_score: NotRequired[float]  # original HNSW score when reranked


class Finding(TypedDict):
    """Single governance or security issue on a changed file."""

    severity: Literal["low", "medium", "high", "critical"]
    category: str
    message: str
    file: str
    citation: str  # policy source or heuristic:dialect / heuristic:pii


class PRReviewState(TypedDict, total=False):
    """Full graph state from ingest through notification."""

    # --- Inputs (set at invoke) ---
    pr_url: str
    repo: str  # owner/name
    pr_number: int
    mode: Literal["advisory", "auto"]

    # --- GitHub ingest ---
    pr_metadata: dict[str, Any]
    changed_files: list[str]
    patches: list[dict[str, Any]]  # filename, patch, status, additions, deletions
    ci_status: dict[str, Any] | None

    # --- RAG ---
    requirements_chunks: list[RetrievalChunk]
    security_policy_chunks: list[RetrievalChunk]

    # --- Analysis ---
    requirements_findings: list[Finding]
    security_findings: list[Finding]
    sast_findings: list[Finding]
    overall_risk: Literal["low", "medium", "high", "blocked"]
    review_markdown: str

    # --- Routing ---
    passed: bool
    blockers: list[str]

    # --- Actions ---
    github_actions_taken: list[str]
    notification_sent: bool
    errors: list[str]
    warnings: list[str]  # e.g. empty Chroma index, LLM fallback

    # --- Observability ---
    token_usage: dict[str, int]  # per eval node invoke count
    node_timings: dict[str, float]  # seconds per node name


def initial_state(
    pr_url: str = "",
    repo: str = "",
    pr_number: int = 0,
    mode: Literal["advisory", "auto"] = "advisory",
) -> PRReviewState:
    """Return a fresh state dict with safe defaults for a new graph run."""
    return PRReviewState(
        pr_url=pr_url,
        repo=repo,
        pr_number=pr_number,
        mode=mode,
        pr_metadata={},
        changed_files=[],
        patches=[],
        ci_status=None,
        requirements_chunks=[],
        security_policy_chunks=[],
        requirements_findings=[],
        security_findings=[],
        sast_findings=[],
        overall_risk="low",
        review_markdown="",
        passed=True,
        blockers=[],
        github_actions_taken=[],
        notification_sent=False,
        errors=[],
        warnings=[],
        token_usage={},
        node_timings={},
    )
