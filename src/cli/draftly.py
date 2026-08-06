from __future__ import annotations

import asyncio
import sys
from typing import Literal
from uuid import uuid4

import structlog
from langchain_core.runnables import RunnableConfig

from src.agents.checkpointer import create_checkpointer
from src.agents.graph import build_hybrid_graph
from src.agents.state import DocumentationState
from src.analytics.events import (
    configure_logging,
    start_flusher,
    start_retention,
    stop_flusher,
    stop_retention,
)
from src.database import close_pool, get_pool

logger = structlog.get_logger()

configure_logging()


async def run_workflow(
    question: str,
    source: Literal["slack", "discord", "github", "cli"] = "cli",
    org_id: str | None = None,
) -> dict:
    if org_id is None:
        print("Error: --org-id is required. Create an org via Clerk first.")
        sys.exit(1)

    await get_pool()
    await start_flusher()
    await start_retention()

    graph_thread_id = f"cli-{hash(question)}"
    workflow_id = str(uuid4())

    initial_state: DocumentationState = {
        "org_id": org_id,
        "source": source,
        "channel_id": "cli",
        "thread_id": f"cli-{uuid4().hex[:12]}",
        "graph_thread_id": graph_thread_id,
        "support_thread_id": "",
        "question": question,
        "similar_threads": [],
        "existing_docs": [],
        "reviewer_feedback_history": [],
        "semantic_context": [],
        "github_context": [],
        "slack_context": [],
        "knowledge_package": {},
        "draft_content": "",
        "draft_title": "",
        "doc_type": "howto",
        "confidence_score": 0.0,
        "review_result": {},
        "review_feedback": "",
        "rubric_feedback": "",
        "rubric_evaluations": [],
        "human_decision": "",
        "human_feedback": "",
        "published_urls": [],
        "reply_errors": [],
        "workflow_id": workflow_id,
        "doc_id": "",
        "messages": [],
        "source_metadata": {},
        "question_type": "unknown",
        "research_skill": {},
        "investigation_plan": [],
        "rubric_status": {},
        "subagent_results": {},
        "message_history": [],
        "_node_traces": [],
        "_trace_collected": False,
        "episode_id": "",
        "reflection_id": "",
        "_reflected": False,
    }

    config: RunnableConfig = {"configurable": {"thread_id": graph_thread_id}}

    async with create_checkpointer() as checkpointer:
        await checkpointer.setup()
        graph = build_hybrid_graph().compile(checkpointer=checkpointer)

        print(f"\n🔄 Processing: {question}\n")

        structlog.contextvars.bind_contextvars(workflow_id=workflow_id, org_id=org_id)
        try:
            result = await graph.ainvoke(initial_state, config)
        finally:
            structlog.contextvars.clear_contextvars()

    if result.get("doc_id"):
        from src.memory.organizations import link_workflow_to_document

        await link_workflow_to_document(workflow_id, result["doc_id"])

    print("\n✅ Completed!")
    print(f"Title: {result.get('draft_title', 'N/A')}")
    print(f"Confidence: {result.get('confidence_score', 0):.2f}")
    print(f"Doc Type: {result.get('doc_type', 'N/A')}")

    if result.get("human_decision"):
        print(f"Human Decision: {result['human_decision']}")

    print(f"\n📄 Draft:\n{result.get('draft_content', 'N/A')[:500]}...")

    await stop_flusher()
    await stop_retention()

    await close_pool()
    return result


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m src.cli.draftly 'your question here' --org-id <clerk_org_id>")
        sys.exit(1)

    question = sys.argv[1]
    org_id = None
    if "--org-id" in sys.argv:
        idx = sys.argv.index("--org-id")
        if idx + 1 < len(sys.argv):
            org_id = sys.argv[idx + 1]

    asyncio.run(run_workflow(question, org_id=org_id))


if __name__ == "__main__":
    main()
