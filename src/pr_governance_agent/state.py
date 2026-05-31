from typing import Any, Literal, NotRequired, TypedDict


class RetrievalChunk(TypedDict):
    id: str
    text: str
    source: str
    section: str
    score: float
    doc_title: NotRequired[str]
    vector_score: NotRequired[float]


class Finding(TypedDict):
    severity: Literal["low", "medium", "high", "critical"]
    category: str
    message: str
    file: str
    citation: str


class PRReviewState(TypedDict, total=False):
    # Inputs
    pr_url: str
    repo: str
    pr_number: int
    mode: Literal["advisory", "auto"]

    # GitHub
    pr_metadata: dict[str, Any]
    changed_files: list[str]
    patches: list[dict[str, Any]]
    ci_status: dict[str, Any] | None

    # RAG
    requirements_chunks: list[RetrievalChunk]
    security_policy_chunks: list[RetrievalChunk]

    # Analysis
    requirements_findings: list[Finding]
    security_findings: list[Finding]
    sast_findings: list[Finding]
    overall_risk: Literal["low", "medium", "high", "blocked"]
    review_markdown: str

    # Routing
    passed: bool
    blockers: list[str]

    # Actions
    github_actions_taken: list[str]
    notification_sent: bool
    errors: list[str]
    warnings: list[str]

    # Observability
    token_usage: dict[str, int]
    node_timings: dict[str, float]


def initial_state(
    pr_url: str = "",
    repo: str = "",
    pr_number: int = 0,
    mode: Literal["advisory", "auto"] = "advisory",
) -> PRReviewState:
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
