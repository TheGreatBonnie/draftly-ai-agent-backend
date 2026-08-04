from __future__ import annotations

import json
from typing import cast

import structlog

from src.database import fetch_one

logger = structlog.get_logger()


async def store_episode(
    org_id: str,
    workflow_id: str,
    source: str,
    input_summary: str,
    outcome: str,
    quality_score: float | None = None,
    duration_ms: int | None = None,
    token_usage: int | None = None,
    thread_id: str | None = None,
    doc_id: str | None = None,
    evidence_ids: list[str] | None = None,
) -> str:
    row = await fetch_one(
        """
        INSERT INTO episodes (
            org_id, workflow_id, thread_id, source, input_summary, evidence_ids,
            doc_id, outcome, quality_score, duration_ms, token_usage
        )
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11)
        RETURNING id::text
        """,
        org_id,
        workflow_id,
        thread_id,
        source,
        input_summary,
        json.dumps(evidence_ids or []),
        doc_id,
        outcome,
        quality_score,
        duration_ms,
        token_usage,
    )
    if row is None:
        raise RuntimeError("episode row missing after insert")
    logger.info("episode_stored", id=row["id"], workflow_id=workflow_id)
    return cast(str, row["id"])
