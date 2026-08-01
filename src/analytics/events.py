"""Structured agent event capture — feeds dashboard telemetry.

A structlog processor snapshots every structured log event into an
in-memory buffer; a background asyncio task drains the buffer into the
``agent_events`` table in batches. The pipeline never blocks on or fails
because of analytics — capture is best-effort, fire-and-forget telemetry.
On shutdown, a flush already in flight when cancellation arrives may lose its
drained batch (best-effort telemetry); buffered events are always flushed by
``stop_flusher``.
"""
from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import MutableMapping
from typing import Any

import structlog

from src.config import settings
from src.database import fetch_all, get_pool

_MAX_STRING_LEN = 2000
_MAX_DETAILS_BYTES = 50_000
_RESERVED_KEYS = {"logger", "timestamp", "exc_info", "stack_info", "record"}
_SELF_TELEMETRY_EVENTS = {
    "events_flushed",
    "event_flush_failed",
    "event_flush_loop_failed",
    "agent_event_retention",
    "agent_event_retention_failed",
}

logger = structlog.get_logger()


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


class EventCollector:
    """Buffers structured log events for batched persistence.

    ``processor`` runs synchronously inside structlog (potentially on any
    thread); ``flush`` runs on the event loop. ``deque.append``/``clear``
    are atomic in CPython, so no lock is needed for telemetry.
    """

    def __init__(self, max_buffer_size: int = 500) -> None:
        self._buffer: deque[dict[str, Any]] = deque(maxlen=max_buffer_size)
        self._dropped = 0

    def processor(
        self,
        _logger: Any,
        _method_name: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        """structlog processor: snapshot each event before rendering."""
        if (
            settings.event_capture_enabled
            and event_dict.get("event") not in _SELF_TELEMETRY_EVENTS
        ):
            try:
                self._buffer.append(self._build_record(dict(event_dict)))
            except Exception:
                self._dropped += 1
                self._buffer.append(
                    {
                        "org_id": None,
                        "workflow_id": None,
                        "event_type": str(event_dict.get("event", "unknown")),
                        "level": str(event_dict.get("level", "info")),
                        "details": {"dropped": True, "reason": "unserializable_details"},
                    }
                )
        return event_dict

    def _build_record(self, event_dict: dict[str, Any]) -> dict[str, Any]:
        org_id = _as_optional_str(event_dict.pop("org_id", None)) or None
        workflow_id = _as_optional_str(event_dict.pop("workflow_id", None)) or None
        event_type = str(event_dict.pop("event", "unknown"))
        level = str(event_dict.pop("level", "info"))
        details = self._sanitize(
            {key: value for key, value in event_dict.items() if key not in _RESERVED_KEYS}
        )
        if len(json.dumps(details, default=str)) > _MAX_DETAILS_BYTES:
            self._dropped += 1
            return {
                "org_id": org_id,
                "workflow_id": workflow_id,
                "event_type": event_type,
                "level": level,
                "details": {"dropped": True, "reason": "details_too_large"},
            }
        return {
            "org_id": org_id,
            "workflow_id": workflow_id,
            "event_type": event_type,
            "level": level,
            "details": details,
        }

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._sanitize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._sanitize(item) for item in value]
        if isinstance(value, str) and len(value) > _MAX_STRING_LEN:
            return value[:_MAX_STRING_LEN] + "...[truncated]"
        return value

    async def flush(self) -> int:
        """Persist buffered events; never raises."""
        if not self._buffer:
            return 0
        events = list(self._buffer)
        self._buffer.clear()
        try:
            await _store_events(events)
        except Exception as e:
            logger.error("event_flush_failed", error=str(e), count=len(events))
            return 0
        logger.info("events_flushed", count=len(events))
        return len(events)


async def _store_events(events: list[dict[str, Any]]) -> None:
    pool = await get_pool()
    await pool.executemany(
        """
        INSERT INTO agent_events (org_id, workflow_id, event_type, level, details)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        """,
        [
            (
                event["org_id"],
                event["workflow_id"],
                event["event_type"],
                event["level"],
                json.dumps(event["details"], default=str),
            )
            for event in events
        ],
    )


collector = EventCollector(max_buffer_size=settings.event_buffer_size)
_flush_task: asyncio.Task[None] | None = None


def configure_logging() -> None:
    """Configure structlog to snapshot every structured event into the collector.

    Replicates structlog's built-in defaults and inserts ``collector.processor``
    between timestamps and rendering. Must run before the first log call.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,  # structlog>=26: lives in structlog.dev
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            collector.processor,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def _flush_loop(interval_seconds: float) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await collector.flush()
        except Exception:
            logger.error("event_flush_loop_failed")


async def start_flusher() -> None:
    """Start the background drain task (idempotent)."""
    global _flush_task
    if _flush_task is not None and not _flush_task.done():
        return
    _flush_task = asyncio.create_task(_flush_loop(settings.event_flush_interval_seconds))


async def stop_flusher() -> None:
    """Cancel the background drain task and flush whatever remains."""
    global _flush_task
    if _flush_task is not None:
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
        _flush_task = None
    await collector.flush()


async def _run_retention_once() -> int:
    """Delete agent_events older than the retention window; returns count."""
    deleted = await fetch_all(
        "DELETE FROM agent_events "
        "WHERE created_at < now() - make_interval(days => $1) RETURNING id",
        settings.event_retention_days,
    )
    return len(deleted)


async def _retention_loop(
    interval_hours: float = 24.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            deleted = await _run_retention_once()
            logger.info("agent_event_retention", deleted=deleted)
        except Exception:
            logger.error("agent_event_retention_failed")
        if stop_event is not None and stop_event.is_set():
            return


_retention_task: asyncio.Task[None] | None = None


async def start_retention() -> None:
    """Start the background retention task (idempotent)."""
    global _retention_task
    if _retention_task is not None and not _retention_task.done():
        return
    _retention_task = asyncio.create_task(_retention_loop())


async def stop_retention() -> None:
    """Cancel the background retention task."""
    global _retention_task
    if _retention_task is not None:
        _retention_task.cancel()
        try:
            await _retention_task
        except asyncio.CancelledError:
            pass
        _retention_task = None
