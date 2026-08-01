from __future__ import annotations

from typing import Any, cast

import structlog
from langchain_cockroachdb import AsyncCockroachDBSaver  # type: ignore[import-untyped]
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.agents.graph import build_hybrid_graph
from src.config import settings
from src.memory.reviewer import get_review_thread_id

logger = structlog.get_logger()


async def resume_review(review_id: str, decision: str, feedback: str = "") -> dict:
    """Resume a paused LangGraph execution after human review.

    Looks up the thread_id from the review_sessions table, recompiles
    the graph with the checkpointer, and sends a Command(resume=...) to
    continue execution from the interrupt() call in human_review_node.
    """
    thread_id = await get_review_thread_id(review_id)
    if not thread_id:
        raise ValueError(f"No thread_id found for review {review_id}")

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    async with AsyncCockroachDBSaver.from_conn_string(settings.cockroachdb_url) as checkpointer:
        await checkpointer.setup()
        graph = build_hybrid_graph().compile(checkpointer=checkpointer)

        logger.info(
            "graph_resuming",
            review_id=review_id,
            thread_id=thread_id,
            decision=decision,
        )

        result = await graph.ainvoke(
            Command(resume={"decision": decision, "feedback": feedback}),
            config,
        )

    logger.info(
        "graph_resumed",
        review_id=review_id,
        decision=decision,
        final_node="publish" if result.get("published_urls") else "end",
    )

    return cast(dict[str, Any], result)
