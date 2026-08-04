from __future__ import annotations

from typing import cast

import structlog
from pydantic import BaseModel, Field

from src.agents.state import DocumentationState
from src.integrations.llm import call_llm_structured
from src.memory.reflections import link_episode_reflection, store_reflection

logger = structlog.get_logger()

_SYSTEM_PROMPT = (
    "You distill one durable lesson from a documentation-agent run. "
    "Output JSON matching the schema: {lesson, confidence, tags}."
)


class ReflectionOutput(BaseModel):
    lesson: str
    confidence: float = Field(ge=0.0, le=1.0)
    tags: list[str] = []


async def reflect_node(state: DocumentationState) -> dict:
    """Persist a per-run reflection. Runs even for failed/rejected runs."""
    episode_id = state.get("episode_id")
    if not episode_id or state.get("_reflected"):
        return {"_reflected": True}

    org_id = state["org_id"]
    outcome = "published" if state.get("published_urls") else "rejected"
    prompt = (
        f"Question: {state.get('question', '')}\n"
        f"Outcome: {outcome}\n"
        f"Final confidence: {state.get('confidence_score', 0)}\n"
        f"Human feedback: {state.get('human_feedback', '')}\n"
        "What lesson should the agent remember from this run?"
    )

    parsed, error = await call_llm_structured(
        prompt,
        ReflectionOutput,
        system_prompt=_SYSTEM_PROMPT,
    )
    if parsed is None:
        logger.warning("reflect_fallback", error=error)
        parsed = ReflectionOutput(lesson="No lesson captured", confidence=0.5, tags=[])
    parsed = cast(ReflectionOutput, parsed)

    try:
        reflection_id = await store_reflection(
            org_id, episode_id, parsed.lesson, parsed.confidence, parsed.tags
        )
        await link_episode_reflection(org_id, episode_id, reflection_id)
    except Exception as e:
        logger.error("reflect_store_failed", error=str(e))
        return {"_reflected": True}

    return {"_reflected": True, "reflection_id": reflection_id}
