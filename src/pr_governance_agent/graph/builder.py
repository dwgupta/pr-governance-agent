from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from pr_governance_agent.config import get_settings
from pr_governance_agent.graph import nodes
from pr_governance_agent.state import PRReviewState


def build_graph() -> StateGraph:
    graph = StateGraph(PRReviewState)

    graph.add_node("ingest_pr", nodes.ingest_pr)
    graph.add_node("rag_requirements", nodes.rag_requirements)
    graph.add_node("rag_security_policies", nodes.rag_security_policies)
    graph.add_node("run_sast_optional", nodes.run_sast_optional)
    graph.add_node("evaluate_requirements", nodes.evaluate_requirements)
    graph.add_node("evaluate_security", nodes.evaluate_security)
    graph.add_node("synthesize_review", nodes.synthesize_review)
    graph.add_node("route_decision", nodes.route_decision)
    graph.add_node("execute_github_advisory", nodes.execute_github_advisory)
    graph.add_node("execute_github_auto", nodes.execute_github_auto)
    graph.add_node("notify_team", nodes.notify_team)

    graph.set_entry_point("ingest_pr")
    graph.add_edge("ingest_pr", "rag_requirements")
    graph.add_edge("rag_requirements", "rag_security_policies")
    graph.add_edge("rag_security_policies", "run_sast_optional")
    graph.add_edge("run_sast_optional", "evaluate_requirements")
    graph.add_edge("evaluate_requirements", "evaluate_security")
    graph.add_edge("evaluate_security", "synthesize_review")
    graph.add_edge("synthesize_review", "route_decision")
    graph.add_edge("route_decision", "execute_github_advisory")
    graph.add_edge("execute_github_advisory", "execute_github_auto")
    graph.add_edge("execute_github_auto", "notify_team")
    graph.add_edge("notify_team", END)

    return graph


def _get_checkpointer():
    settings = get_settings()
    if settings.use_sqlite_checkpoint:
        try:
            import sqlite3

            from langgraph.checkpoint.sqlite import SqliteSaver

            settings.checkpoint_dir.mkdir(parents=True, exist_ok=True)
            db_path = settings.checkpoint_dir / "checkpoints.db"
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            return SqliteSaver(conn)
        except ImportError:
            pass
    return MemorySaver()


def compile_graph():
    graph = build_graph()
    return graph.compile(checkpointer=_get_checkpointer())
