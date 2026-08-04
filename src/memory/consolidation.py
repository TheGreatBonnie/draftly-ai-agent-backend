from __future__ import annotations

import structlog

from src.database import fetch_all
from src.memory.reflections import increment_reflection_frequency, store_reflection

logger = structlog.get_logger()


def _lesson_from_episode(input_summary: str) -> str:
    return (input_summary or "").strip()[:140]


async def consolidate(org_id: str) -> int:
    """Stub consolidation: one reflection per unique episode lesson (no LLM yet)."""
    episodes = await fetch_all(
        """
        SELECT id::text as id, input_summary
        FROM episodes
        WHERE org_id = $1
          AND created_at > now() - interval '7 days'
          AND NOT EXISTS (
              SELECT 1 FROM reflections r
              WHERE r.org_id = episodes.org_id AND r.episode_id = episodes.id
          )
        ORDER BY created_at ASC
        """,
        org_id,
    )

    seen: set[str] = set()
    stored = 0
    for ep in episodes:
        lesson = _lesson_from_episode(ep.get("input_summary") or "")
        if not lesson:
            continue
        normalized = lesson.lower()
        if normalized in seen:
            await increment_reflection_frequency(ep["id"])
            continue
        seen.add(normalized)
        await store_reflection(org_id, ep["id"], lesson, 0.6, ["consolidated"])
        stored += 1
    logger.info("consolidation_complete", org_id=org_id, stored=stored)
    return stored
