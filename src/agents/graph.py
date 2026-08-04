from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog
from langgraph.graph import END, StateGraph

from src.agents.nodes.human import human_review_node
from src.agents.nodes.memory import memory_retrieve_node
from src.agents.nodes.publish import publish_node
from src.agents.nodes.synthesize import synthesize_node
from src.agents.nodes.write import write_docs_node
from src.agents.state import DocumentationState
from src.analytics.traces import AgentTrace, NodeTrace, TraceCollector
from src.memory.episodes import store_episode

logger = structlog.get_logger()

_trace_collector: TraceCollector | None = None

def set_trace_collector(collector: TraceCollector) -> None:
    global _trace_collector
    _trace_collector = collector


async def collect_trace_node(state: DocumentationState) -> dict:
    """Collect final trace after pipeline completion and persist an episode."""
    global _trace_collector

    result: dict = {"_trace_collected": True}

    node_traces: list[NodeTrace] = state.get("_node_traces", []) or []
    outcome = "published" if state.get("published_urls") else "rejected"
    try:
        episode_id = await store_episode(
            org_id=state["org_id"],
            workflow_id=state.get("workflow_id", ""),
            source=state.get("source", "cli"),
            input_summary=state["question"],
            outcome=outcome,
            quality_score=state.get("confidence_score", 0),
            duration_ms=int(sum(t.duration_ms for t in node_traces)),
        )
        result["episode_id"] = episode_id
    except Exception as e:
        logger.error("episode_store_failed", error=str(e))

    if _trace_collector is None:
        return result

    try:
        trace = AgentTrace(
            trace_id=str(uuid4()),
            org_id=state["org_id"],
            workflow_id=state.get("workflow_id", ""),
            question=state["question"],
            question_type=state.get("question_type", "unknown"),
            source=state.get("source", "cli"),
            nodes_executed=[t.node_name for t in node_traces],
            node_traces=node_traces,
            total_duration_ms=sum(t.duration_ms for t in node_traces),
            final_confidence=state.get("confidence_score", 0),
            rubric_results=state.get("rubric_evaluations", []) or [],
            published=bool(state.get("published_urls")),
            publish_urls=state.get("published_urls", []),
        )
        await _trace_collector.collect(trace)
    except Exception as e:
        logger.error("trace_collection_failed", error=str(e))

    return result


def _wrap_node_with_tracing(
    node_name: str,
    node_fn: Callable[[DocumentationState], Awaitable[dict]],
) -> Any:
    """Wrap a graph node to capture timing and I/O snapshots."""
    async def traced_node(state: DocumentationState) -> dict:
        start_time = datetime.utcnow()
        error = None
        try:
            result = await node_fn(state)
            return result
        except Exception as e:
            error = str(e)
            raise
        finally:
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            node_trace = NodeTrace(
                node_name=node_name,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                error=error,
            )
            if "_node_traces" not in state:
                state["_node_traces"] = []
            state["_node_traces"].append(node_trace)

    return traced_node


def build_hybrid_graph() -> StateGraph:
    """Build enhanced graph with Deep agents capabilities and trace collection."""
    from src.agents.nodes.ingest import ingest_node_hybrid
    from src.agents.nodes.research import research_node_hybrid
    from src.agents.nodes.review import ai_review_node_hybrid

    graph = StateGraph(DocumentationState)

    node_defs = {
        "ingest": ingest_node_hybrid,
        "memory_retrieve": memory_retrieve_node,
        "research": research_node_hybrid,
        "synthesize": synthesize_node,
        "write_docs": write_docs_node,
        "ai_review": ai_review_node_hybrid,
        "human_review": human_review_node,
        "publish": publish_node,
    }

    for name, fn in node_defs.items():
        graph.add_node(name, _wrap_node_with_tracing(name, fn))

    graph.add_node("collect_trace", collect_trace_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "memory_retrieve")
    graph.add_edge("memory_retrieve", "research")
    graph.add_edge("research", "synthesize")
    graph.add_edge("synthesize", "write_docs")
    graph.add_edge("write_docs", "ai_review")

    graph.add_conditional_edges(
        "ai_review",
        lambda state: route_by_rubric(state),
        {
            "human_review": "human_review",
            "research": "research",
            "write_docs": "write_docs",
            "publish": "publish",
        },
    )

    graph.add_conditional_edges(
        "human_review",
        lambda state: {
            "approve": "publish",
            "approved": "publish",
            "reject": "collect_trace",
            "rejected": "collect_trace",
            "revise": "write_docs",
            "needs_changes": "write_docs",
        }.get(state.get("human_decision", ""), "collect_trace"),
    )

    graph.add_edge("publish", "collect_trace")
    graph.add_edge("collect_trace", END)

    logger.info("hybrid_graph_built_with_tracing")
    return graph


def route_by_rubric(state: DocumentationState) -> str:
    rubric_status = state.get("rubric_status", {})
    if rubric_status.get("needs_revision"):
        if rubric_status.get("research_needed"):
            return "research"
        return "write_docs"
    return "human_review"
