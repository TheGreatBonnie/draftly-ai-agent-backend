from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import cast

import structlog

from src.database import execute, fetch_all, fetch_one

logger = structlog.get_logger()


def _serialize_row(row: dict) -> dict:
    return {
        k: str(v) if isinstance(v, uuid.UUID) else v.isoformat() if isinstance(v, datetime) else v
        for k, v in dict(row).items()
    }


async def create_review_session(
    doc_id: str,
    reviewer_id: str | None = None,
    confidence_before: float | None = None,
    graph_thread_id: str = "",
) -> str:
    row = await fetch_one(
        """
        INSERT INTO review_sessions (doc_id, reviewer_id, confidence_before, status, thread_id)
        VALUES ($1, $2, $3, 'pending', $4)
        RETURNING id::text
        """,
        doc_id,
        reviewer_id,
        confidence_before,
        graph_thread_id,
    )
    if row is None:
        raise RuntimeError("review session row missing after insert")
    logger.info("review_created", id=row["id"], doc_id=doc_id)
    return cast(str, row["id"])


async def complete_review(
    review_id: str,
    status: str,
    feedback: str | None = None,
    edits_made: dict | None = None,
    confidence_after: float | None = None,
) -> None:
    await execute(
        """
        UPDATE review_sessions
        SET status = $1, reviewer_feedback = $2, edits_made = $3::jsonb,
            confidence_after = $4, completed_at = now()
        WHERE id = $5
        """,
        status,
        feedback,
        json.dumps(edits_made or {}),
        confidence_after,
        review_id,
    )
    logger.info("review_completed", id=review_id, status=status)


async def get_pending_reviews(org_id: str) -> list[dict]:
    rows = await fetch_all(
        """
        SELECT rs.*, rs.id::text as id, d.title, d.content, d.doc_type, d.confidence_score,
               st.question_summary as original_question, st.source as platform
        FROM review_sessions rs
        JOIN documentation d ON d.id = rs.doc_id
        LEFT JOIN support_threads st ON d.source_thread_id = st.id
        WHERE d.org_id = $1 AND rs.status = 'pending'
        ORDER BY rs.created_at DESC
        """,
        org_id,
    )
    return [_serialize_row(r) for r in rows]


async def get_all_reviews(org_id: str) -> list[dict]:
    rows = await fetch_all(
        """
        SELECT rs.*, rs.id::text as id, d.title, d.content, d.doc_type, d.confidence_score,
               st.question_summary as original_question, st.source as platform
        FROM review_sessions rs
        JOIN documentation d ON d.id = rs.doc_id
        LEFT JOIN support_threads st ON d.source_thread_id = st.id
        WHERE d.org_id = $1
        ORDER BY rs.created_at DESC
        """,
        org_id,
    )
    return [_serialize_row(r) for r in rows]


async def get_review_history(org_id: str, limit: int = 10) -> list[dict]:
    rows = await fetch_all(
        """
        SELECT rs.*, rs.id::text as id, d.title, d.doc_type
        FROM review_sessions rs
        JOIN documentation d ON d.id = rs.doc_id
        WHERE d.org_id = $1 AND rs.status != 'pending'
        ORDER BY rs.completed_at DESC
        LIMIT $2
        """,
        org_id,
        limit,
    )
    return [_serialize_row(r) for r in rows]


async def get_reviewer_memory(org_id: str, limit: int = 10) -> list[dict]:
    rows = await fetch_all(
        """
        SELECT * FROM agent_memory
        WHERE org_id = $1 AND memory_type = 'reviewer'
        ORDER BY created_at DESC
        LIMIT $2
        """,
        org_id,
        limit,
    )
    return [_serialize_row(r) for r in rows]


async def get_pending_review_by_doc(doc_id: str) -> dict | None:
    """Check if a pending review session already exists for a document."""
    row = await fetch_one(
        "SELECT id::text, status FROM review_sessions WHERE doc_id = $1 LIMIT 1",
        doc_id,
    )
    return _serialize_row(row) if row else None


async def get_review_thread_id(review_id: str) -> str | None:
    """Look up the graph thread_id from a review session for HITL resume."""
    row = await fetch_one(
        "SELECT thread_id FROM review_sessions WHERE id = $1",
        review_id,
    )
    return row["thread_id"] if row and row["thread_id"] else None
