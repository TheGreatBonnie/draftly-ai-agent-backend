from __future__ import annotations

from typing import cast

import structlog

from src.database import execute, fetch_one

logger = structlog.get_logger()


async def store_reflection(
    org_id: str,
    episode_id: str,
    lesson: str,
    confidence: float,
    tags: list[str] | None = None,
) -> str:
    row = await fetch_one(
        """
        INSERT INTO reflections (org_id, episode_id, lesson, confidence, tags)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id::text
        """,
        org_id,
        episode_id,
        lesson,
        confidence,
        tags or [],
    )
    if row is None:
        raise RuntimeError("reflection row missing after insert")
    logger.info("reflection_stored", id=row["id"], episode_id=episode_id)
    return cast(str, row["id"])


async def link_episode_reflection(
    org_id: str, episode_id: str, reflection_id: str
) -> None:
    await execute(
        """
        INSERT INTO memory_links (org_id, from_type, from_id, to_type, to_id, relation)
        VALUES ($1, 'episode', $2, 'reflection', $3, 'yields_reflection')
        """,
        org_id,
        episode_id,
        reflection_id,
    )
