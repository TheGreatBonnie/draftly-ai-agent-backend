from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from src.config import settings
from src.database import fetch_all, transaction
from src.integrations.llm import call_llm_structured
from src.memory.reflections import (
    find_active_reflection,
    increment_reflection_frequency,
    link_episode_reflection,
    store_reflection,
)

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You distill durable, cross-episode lessons from documentation-agent "
    "episodes. Output JSON matching the schema: "
    "{reflections: [{lesson, confidence, tags, episode_indices}]}. "
    "episode_indices are 0-based positions into the provided numbered list. "
    "Skip run-specific or trivially duplicated lessons."
)


class ConsolidatedReflection(BaseModel):
    lesson: str
    confidence: float = Field(ge=0.0, le=1.0)
    tags: list[str] = []
    episode_indices: list[int] = []


class ConsolidationOutput(BaseModel):
    reflections: list[ConsolidatedReflection] = []


def _batch_episodes(episodes: list[dict], size: int) -> list[list[dict]]:
    return [episodes[i : i + size] for i in range(0, len(episodes), size)]


def _build_prompt(batch: list[dict]) -> str:
    lines = [
        f"{i}. {ep.get('input_summary') or '(no summary)'}"
        for i, ep in enumerate(batch)
    ]
    return (
        "Here are the most recent documentation-agent episodes:\n"
        + "\n".join(lines)
        + "\n\nDistill the durable lessons. For each lesson, list the episode "
        "indices it synthesizes (0-based)."
    )


async def consolidate(org_id: str) -> int:
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

    stored = 0
    for batch in _batch_episodes(episodes, settings.consolidation_batch_size):
        parsed, error = await call_llm_structured(
            _build_prompt(batch),
            ConsolidationOutput,
            system_prompt=_SYSTEM_PROMPT,
            model=settings.llm_model,
            provider="requesty",
            temperature=0.0,
        )
        if not isinstance(parsed, ConsolidationOutput):
            logger.warning("consolidation_llm_failed", org_id=org_id, error=error)
            continue

        async with transaction() as conn:
            for reflection in parsed.reflections:
                lesson = reflection.lesson.strip()
                if not lesson:
                    continue
                existing = await find_active_reflection(org_id, lesson, conn=conn)
                if existing is not None:
                    await increment_reflection_frequency(existing, conn=conn)
                    continue
                reflection_id = await store_reflection(
                    org_id, None, lesson, reflection.confidence, reflection.tags,
                    conn=conn,
                )
                stored += 1
                for idx in reflection.episode_indices:
                    if 0 <= idx < len(batch):
                        await link_episode_reflection(
                            org_id, batch[idx]["id"], reflection_id, conn=conn
                        )

    logger.info("consolidation_complete", org_id=org_id, stored=stored)
    return stored
