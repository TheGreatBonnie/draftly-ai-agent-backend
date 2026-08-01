from __future__ import annotations

import structlog

from src.agents.planners.investigation import _classify_complexity
from src.agents.skills import get_skill_for_question, select_documentation_type
from src.agents.state import DocumentationState
from src.memory.episodic import create_thread
from src.memory.organizational import store_audit_log

logger = structlog.get_logger()


async def ingest_node_hybrid(state: DocumentationState) -> dict:
    """Enhanced ingest node with skill selection and question classification."""
    # Local imports moved to module level for consistency and linting

    org_id = state["org_id"]
    source = state["source"]
    channel_id = state["channel_id"]
    thread_id = state["thread_id"]
    question = state["question"]

    logger.info("ingest_hybrid_started", org_id=org_id, source=source, thread_id=thread_id)

    # Create support thread record
    st_id = await create_thread(
        org_id=org_id,
        source=source,
        channel_id=channel_id,
        thread_id=thread_id,
        title=question[:200] if question else None,
        question_summary=question,
    )

    # Audit log
    await store_audit_log(
        org_id=org_id,
        actor="agent",
        action="ingest_message",
        resource_type="support_thread",
        resource_id=st_id,
        details={"source": source, "thread_id": thread_id, "question": question[:500]},
    )

    # Classify question complexity
    question_type = await _classify_complexity(question)

    # Select appropriate documentation type
    doc_type = select_documentation_type(question)

    # Get research skill
    research_skill = get_skill_for_question(question, "research")

    logger.info(
        "ingest_hybrid_completed",
        thread_record_id=st_id,
        question_type=question_type,
        doc_type=doc_type,
    )

    return {
        "support_thread_id": st_id,
        "similar_threads": [],
        "existing_docs": [],
        "reviewer_feedback_history": [],
        "semantic_context": [],
        "github_context": [],
        "slack_context": [],
        "knowledge_package": {},
        "draft_content": "",
        "draft_title": "",
        "doc_type": doc_type,
        "confidence_score": 0.0,
        "review_result": {},
        "review_feedback": "",
        "human_decision": "",
        "human_feedback": "",
        "published_urls": [],
        "messages": [],
        "question_type": question_type,
        "research_skill": research_skill,
    }
