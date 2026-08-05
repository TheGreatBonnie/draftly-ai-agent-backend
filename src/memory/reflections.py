from __future__ import annotations

from typing import Any, cast

import structlog

from src.database import execute, execute_conn, fetch_one, fetch_one_conn

logger = structlog.get_logger()


async def store_reflection(
    org_id: str,
    episode_id: str | None,
    lesson: str,
    confidence: float,
    tags: list[str] | None = None,
    conn: Any = None,
) -> str:
    query = """
        INSERT INTO reflections (org_id, episode_id, lesson, confidence, tags)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id::text
        """
    args = (org_id, episode_id, lesson, confidence, tags or [])
    if conn is not None:
        row = await fetch_one_conn(conn, query, *args)
    else:
        row = await fetch_one(query, *args)
    if row is None:
        raise RuntimeError("reflection row missing after insert")
    logger.info("reflection_stored", id=row["id"], episode_id=episode_id)
    return cast(str, row["id"])


async def find_active_reflection(
    org_id: str, lesson: str, conn: Any = None
) -> str | None:
    query = """
        SELECT id::text FROM reflections
        WHERE org_id = $1 AND status = 'active' AND lower(lesson) = lower($2)
        """
    if conn is not None:
        row = await fetch_one_conn(conn, query, org_id, lesson)
    else:
        row = await fetch_one(query, org_id, lesson)
    return cast(str | None, row["id"] if row else None)


async def increment_reflection_frequency(reflection_id: str, conn: Any = None) -> None:
    query = "UPDATE reflections SET frequency = frequency + 1 WHERE id = $1"
    if conn is not None:
        await execute_conn(conn, query, reflection_id)
    else:
        await execute(query, reflection_id)


async def link_episode_reflection(
    org_id: str, episode_id: str, reflection_id: str, conn: Any = None
) -> None:
    query = """
        INSERT INTO memory_links (org_id, from_type, from_id, to_type, to_id, relation)
        VALUES ($1, 'episode', $2, 'reflection', $3, 'yields_reflection')
        """
    if conn is not None:
        await execute_conn(conn, query, org_id, episode_id, reflection_id)
    else:
        await execute(query, org_id, episode_id, reflection_id)
