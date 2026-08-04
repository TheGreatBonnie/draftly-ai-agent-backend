from __future__ import annotations

import asyncio

import structlog

from src.config import settings
from src.memory.consolidation import consolidate

logger = structlog.get_logger()


async def _run_consolidation_once(org_ids: list[str]) -> None:
    if not settings.consolidation_enabled:
        return
    for org_id in org_ids:
        try:
            await consolidate(org_id)
        except Exception:
            logger.error("consolidation_failed", org_id=org_id)


async def _consolidation_loop(org_ids: list[str]) -> None:
    while True:
        await asyncio.sleep(settings.consolidation_interval_hours * 3600)
        await _run_consolidation_once(org_ids)


_consolidation_task: asyncio.Task[None] | None = None


async def start_consolidation(org_ids: list[str]) -> None:
    global _consolidation_task
    if _consolidation_task is not None and not _consolidation_task.done():
        return
    _consolidation_task = asyncio.create_task(_consolidation_loop(org_ids))


async def stop_consolidation() -> None:
    global _consolidation_task
    if _consolidation_task is not None:
        _consolidation_task.cancel()
        try:
            await _consolidation_task
        except asyncio.CancelledError:
            pass
        _consolidation_task = None
