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
        k: str(v) if isinstance(v, uuid.UUID)
        else v.isoformat() if isinstance(v, datetime)
        else v
        for k, v in dict(row).items()
    }


async def create_thread(
    org_id: str,
    source: str,
    channel_id: str,
    thread_id: str,
    title: str | None = None,
    question_summary: str | None = None,
    participants: list | None = None,
) -> str:
    row = await fetch_one(
        """
        INSERT INTO support_threads
            (org_id, source, channel_id, thread_id, title, question_summary, participants)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        RETURNING id::text
        """,
        org_id,
        source,
        channel_id,
        thread_id,
        title,
        question_summary,
        json.dumps(participants or []),
    )
    if row is None:
        raise RuntimeError("thread row missing after insert")
    logger.info("thread_created", id=row["id"], source=source)
    return cast(str, row["id"])


async def get_thread(thread_id: str) -> dict | None:
    row = await fetch_one("SELECT *, id::text as id FROM support_threads WHERE id = $1", thread_id)
    return dict(row) if row else None


async def search_threads(org_id: str, query: str, limit: int = 10) -> list[dict]:
    rows = await fetch_all(
        """
        SELECT *, id::text as id FROM support_threads
        WHERE org_id = $1
        AND plainto_tsquery('english', $2) @@
            to_tsvector('english',
                COALESCE(question_summary, '') || ' '
                || COALESCE(title, ''))
        ORDER BY created_at DESC
        LIMIT $3
        """,
        org_id,
        query,
        limit,
    )
    return [_serialize_row(r) for r in rows]


async def resolve_thread(thread_id: str, resolution: str) -> None:
    await execute(
        """
        UPDATE support_threads
        SET status = 'resolved', resolution = $1, resolved_at = now()
        WHERE id = $2
        """,
        resolution,
        thread_id,
    )
    logger.info("thread_resolved", id=thread_id)


async def get_recent_threads(org_id: str, limit: int = 20) -> list[dict]:
    rows = await fetch_all(
        """
        SELECT *, id::text as id FROM support_threads
        WHERE org_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        org_id,
        limit,
    )
    return [_serialize_row(r) for r in rows]
