from __future__ import annotations

import re

import structlog

from src.agents.state import DocumentationState
from src.memory.episodic import search_threads
from src.memory.organizational import search_memory
from src.memory.reviewer import get_reviewer_memory
from src.memory.vector_store import search_similar

logger = structlog.get_logger()


async def memory_retrieve_node(state: DocumentationState) -> dict:
    org_id = state["org_id"]
    question = state["question"]

    logger.info("memory_retrieve_started", org_id=org_id)

    # 1. Semantic search via Distributed Vector Index
    semantic_results = await search_similar(org_id, question, k=10)

    # 2. Episodic search — similar support threads
    sanitized = re.sub(r'[^\w\s]', ' ', question)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    episodic_results = await search_threads(org_id, sanitized, limit=5)

    # 3. Organizational memory — best practices, known solutions
    pattern = question.split()[0] if question else ""
    org_results = await search_memory(org_id, key_pattern=pattern, limit=5)

    # 4. Reviewer memory — past feedback
    reviewer_results = await get_reviewer_memory(org_id, limit=5)

    # 5. Search for existing documentation on this topic
    existing_docs = [r for r in semantic_results if r["content_type"] == "documentation"]

    logger.info(
        "memory_retrieve_completed",
        semantic=len(semantic_results),
        episodic=len(episodic_results),
        organizational=len(org_results),
        reviewer=len(reviewer_results),
        existing_docs=len(existing_docs),
    )

    return {
        "similar_threads": [dict(r) for r in episodic_results],
        "existing_docs": existing_docs,
        "reviewer_feedback_history": [dict(r) for r in reviewer_results],
        "semantic_context": semantic_results,
    }
