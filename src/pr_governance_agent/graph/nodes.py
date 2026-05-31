from __future__ import annotations

from pr_governance_agent.config import get_settings
from pr_governance_agent.graph.llm import evaluate_with_llm_or_heuristic
from pr_governance_agent.metrics.usage import track_node
from pr_governance_agent.mcp.github_client import GitHubClient, parse_pr_url
from pr_governance_agent.notifications.email import send_notification
from pr_governance_agent.rag.chroma_store import REQUIREMENTS_COLLECTION, SECURITY_COLLECTION, ChromaStore
from pr_governance_agent.security.sast_runner import run_semgrep_on_patches
from pr_governance_agent.state import Finding, PRReviewState


def ingest_pr(state: PRReviewState) -> PRReviewState:
    with track_node(state, "ingest_pr"):
        errors = list(state.get("errors") or [])
        try:
            pr_url = state.get("pr_url") or ""
            if pr_url:
                full_repo, _, number = parse_pr_url(pr_url)
                state["repo"] = full_repo
                state["pr_number"] = number

            client = GitHubClient()
            if pr_url:
                data = client.fetch_pr(pr_url)
            else:
                data = client.fetch_pr("https://github.com/demo/migration-sandbox/pull/1")

            state["pr_metadata"] = data.get("pr_metadata", {})
            state["changed_files"] = data.get("changed_files", [])
            state["patches"] = data.get("patches", [])
            state["ci_status"] = data.get("ci_status")
            state["repo"] = data.get("repo", state.get("repo", ""))
            state["pr_number"] = data.get("pr_number", state.get("pr_number", 0))
        except Exception as exc:
            errors.append(f"ingest_pr: {exc}")
            state["errors"] = errors
    return state


def _build_rag_query(state: PRReviewState) -> str:
    meta = state.get("pr_metadata") or {}
    files = ", ".join(state.get("changed_files") or [])
    return f"{meta.get('title', '')} {meta.get('body', '')} files: {files}"


def rag_requirements(state: PRReviewState) -> PRReviewState:
    with track_node(state, "rag_requirements"):
        settings = get_settings()
        store = ChromaStore()
        state["requirements_chunks"] = store.retrieve(
            REQUIREMENTS_COLLECTION,
            _build_rag_query(state),
            retrieve_n=settings.rag_retrieve_n,
            top_k=settings.rag_top_k,
        )
    return state


def rag_security_policies(state: PRReviewState) -> PRReviewState:
    with track_node(state, "rag_security_policies"):
        settings = get_settings()
        store = ChromaStore()
        state["security_policy_chunks"] = store.retrieve(
            SECURITY_COLLECTION,
            _build_rag_query(state),
            retrieve_n=settings.rag_retrieve_n,
            top_k=settings.rag_top_k,
        )
    return state


def run_sast_optional(state: PRReviewState) -> PRReviewState:
    with track_node(state, "run_sast_optional"):
        settings = get_settings()
        if settings.enable_sast:
            state["sast_findings"] = run_semgrep_on_patches(state.get("patches") or [])
        else:
            state["sast_findings"] = []
    return state


def evaluate_requirements(state: PRReviewState) -> PRReviewState:
    with track_node(state, "evaluate_requirements"):
        state["requirements_findings"] = evaluate_with_llm_or_heuristic(
            state,
            "requirements",
            state.get("requirements_chunks") or [],
        )
    return state


def evaluate_security(state: PRReviewState) -> PRReviewState:
    with track_node(state, "evaluate_security"):
        policy = evaluate_with_llm_or_heuristic(
            state,
            "security",
            state.get("security_policy_chunks") or [],
        )
        sast = state.get("sast_findings") or []
        state["security_findings"] = policy + list(sast)
    return state


def synthesize_review(state: PRReviewState) -> PRReviewState:
    with track_node(state, "synthesize_review"):
        req = state.get("requirements_findings") or []
        sec = state.get("security_findings") or []
        meta = state.get("pr_metadata") or {}

        lines = [
            f"# PR Review: {meta.get('title', 'Untitled')}",
            f"**Repo:** {state.get('repo')} | **PR:** #{state.get('pr_number')}",
            f"**Mode:** {state.get('mode', 'advisory')}",
            "",
            "## Requirements findings",
        ]
        if req:
            for f in req:
                lines.append(
                    f"- [{f['severity'].upper()}] {f['file']}: {f['message']} ({f['citation']})"
                )
        else:
            lines.append("- None")

        lines.extend(["", "## Security findings"])
        if sec:
            for f in sec:
                lines.append(
                    f"- [{f['severity'].upper()}] {f['file']}: {f['message']} ({f['citation']})"
                )
        else:
            lines.append("- None")

        lines.extend(["", "## Retrieved policy context"])
        for c in (state.get("requirements_chunks") or [])[:3]:
            lines.append(f"- Requirements: [{c['source']}] {c['section']}")
        for c in (state.get("security_policy_chunks") or [])[:3]:
            lines.append(f"- Security: [{c['source']}] {c['section']}")

        state["review_markdown"] = "\n".join(lines)
    return state


def route_decision(state: PRReviewState) -> PRReviewState:
    with track_node(state, "route_decision"):
        req = state.get("requirements_findings") or []
        sec = state.get("security_findings") or []
        blockers: list[str] = []

        severities = [f["severity"] for f in req + sec]
        if any(s in ("high", "critical") for s in severities):
            blockers.append("High or critical findings present")

        state["blockers"] = blockers
        state["passed"] = len(blockers) == 0

        if any(s == "critical" for s in severities):
            state["overall_risk"] = "blocked"
        elif any(s == "high" for s in severities):
            state["overall_risk"] = "high"
        elif any(s == "medium" for s in severities):
            state["overall_risk"] = "medium"
        else:
            state["overall_risk"] = "low"
    return state


def execute_github_advisory(state: PRReviewState) -> PRReviewState:
    with track_node(state, "execute_github_advisory"):
        settings = get_settings()
        actions = list(state.get("github_actions_taken") or [])
        review = state.get("review_markdown") or ""

        if settings.post_pr_comments and state.get("repo") and state.get("pr_number"):
            try:
                client = GitHubClient()
                action = client.post_comment(
                    state["repo"],
                    int(state["pr_number"]),
                    review[:60000],
                )
                actions.append(action)
            except Exception as exc:
                errors = list(state.get("errors") or [])
                errors.append(f"post_comment: {exc}")
                state["errors"] = errors
        else:
            actions.append("advisory_review_generated")

        state["github_actions_taken"] = actions
    return state


def execute_github_auto(state: PRReviewState) -> PRReviewState:
    with track_node(state, "execute_github_auto"):
        settings = get_settings()
        actions = list(state.get("github_actions_taken") or [])
        mode = state.get("mode", "advisory")
        repo = state.get("repo", "")
        pr_number = int(state.get("pr_number") or 0)

        if (
            state.get("passed")
            and mode == "auto"
            and settings.writes_allowed(repo, mode)
            and pr_number
        ):
            try:
                client = GitHubClient()
                actions.append(client.approve_pr(repo, pr_number))
                actions.append(client.merge_pr(repo, pr_number))
            except Exception as exc:
                errors = list(state.get("errors") or [])
                errors.append(f"auto_actions: {exc}")
                state["errors"] = errors
        elif mode == "auto" and not settings.writes_allowed(repo, mode):
            actions.append("auto_skipped_writes_not_allowed")
        elif mode != "auto":
            actions.append("auto_skipped_advisory_mode")
        else:
            actions.append("auto_skipped_failed_checks")

        state["github_actions_taken"] = actions
    return state


def notify_team(state: PRReviewState) -> PRReviewState:
    with track_node(state, "notify_team"):
        passed = bool(state.get("passed"))
        subject = (
            f"PR #{state.get('pr_number')} governance {'PASSED' if passed else 'FAILED'}"
        )
        body = state.get("review_markdown") or ""
        if state.get("blockers"):
            body += "\n\nBlockers:\n" + "\n".join(f"- {b}" for b in state["blockers"])
        state["notification_sent"] = send_notification(subject, body, passed=passed)
    return state
