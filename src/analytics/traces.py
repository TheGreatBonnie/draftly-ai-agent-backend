from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import structlog

from src.config import settings
from src.database import execute, fetch_all

logger = structlog.get_logger()

_FlushCallback = Callable[[], Coroutine[Any, Any, Any | None]]


async def _purge_expired_traces() -> int:
    """Delete agent_traces older than the retention window; returns count."""
    rows = await fetch_all(
        "DELETE FROM agent_traces "
        "WHERE created_at < now() - ($1::INT * INTERVAL '1 day') RETURNING id",
        settings.trace_retention_days,
    )
    return len(rows)


async def _trace_retention_loop(
    interval_hours: float = 24.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            deleted = await _purge_expired_traces()
            logger.info("trace_retention", deleted=deleted)
        except Exception:
            logger.error("trace_retention_failed")
        if stop_event is not None and stop_event.is_set():
            return


_trace_retention_task: asyncio.Task[None] | None = None


async def start_trace_retention() -> None:
    global _trace_retention_task
    if _trace_retention_task is not None and not _trace_retention_task.done():
        return
    _trace_retention_task = asyncio.create_task(_trace_retention_loop())


async def stop_trace_retention() -> None:
    global _trace_retention_task
    if _trace_retention_task is not None:
        _trace_retention_task.cancel()
        try:
            await _trace_retention_task
        except asyncio.CancelledError:
            pass
        _trace_retention_task = None


@dataclass
class NodeTrace:
    node_name: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_ms: float = 0.0
    input_state: dict | None = None
    output_state: dict | None = None
    error: str | None = None
    token_usage: int = 0
    succeeded: bool = True


def _sanitize_state(state: Mapping[str, Any] | None) -> dict:
    """Keep traces compact + PII-safe: drop raw content, cap value length."""
    if not state:
        return {}
    max_len = 2000
    drop_keys = {"draft_content", "knowledge_package", "message_history", "subagent_results"}
    out: dict[str, Any] = {}
    for k, v in state.items():
        if k in drop_keys:
            continue
        text = json.dumps(v, default=str)
        out[k] = text[:max_len]
    return out


@dataclass
class AgentTrace:
    trace_id: str
    org_id: str
    workflow_id: str
    question: str
    question_type: str
    source: str
    nodes_executed: list[str] = field(default_factory=list)
    node_traces: list[NodeTrace] = field(default_factory=list)
    total_duration_ms: float = 0.0
    rubric_results: list[dict] = field(default_factory=list)
    verification_results: list[dict] = field(default_factory=list)
    human_decisions: list[dict] = field(default_factory=list)
    final_confidence: float = 0.0
    published: bool = False
    publish_urls: list[dict] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


class TraceCollector:
    def __init__(self, flush_threshold: int = 100):
        self._buffer: list[AgentTrace] = []
        self._flush_threshold = flush_threshold
        self._on_flush_callback: _FlushCallback | None = None

    def set_on_flush_callback(self, callback: _FlushCallback) -> None:
        self._on_flush_callback = callback

    async def collect(self, trace: AgentTrace) -> None:
        self._buffer.append(trace)
        if len(self._buffer) >= self._flush_threshold:
            await self.flush()

    async def flush(self) -> None:
        if not self._buffer:
            return
        traces = self._buffer.copy()
        self._buffer.clear()
        try:
            await _store_traces(traces)
            logger.info("traces_flushed", count=len(traces))
            if self._on_flush_callback:
                await self._on_flush_callback()
        except Exception as e:
            logger.error("trace_flush_failed", error=str(e))

    async def get_traces_for_analysis(
        self,
        org_id: str,
        time_window: timedelta | None = None,
        min_confidence: float = 0.0,
        max_confidence: float = 1.0,
    ) -> list[AgentTrace]:
        rows = await fetch_all(
            """
            SELECT trace_data, created_at
            FROM agent_traces
            WHERE org_id = $1
              AND (trace_data->>'final_confidence')::FLOAT >= $2
              AND (trace_data->>'final_confidence')::FLOAT <= $3
              AND ($4::TIMESTAMPTZ IS NULL OR created_at >= $4)
            ORDER BY created_at DESC
            """,
            org_id,
            min_confidence,
            max_confidence,
            datetime.utcnow() - time_window if time_window else None,
        )
        return [_dict_to_trace(row["trace_data"]) for row in rows]


def _trace_to_payload(trace: AgentTrace) -> str:
    """Serialize a trace into its persisted JSON payload."""
    return json.dumps(
        {
            "question": trace.question,
            "question_type": trace.question_type,
            "source": trace.source,
            "nodes_executed": trace.nodes_executed,
            "node_traces": [
                {
                    "node_name": nt.node_name,
                    "start_time": nt.start_time,
                    "end_time": nt.end_time,
                    "duration_ms": nt.duration_ms,
                    "token_usage": nt.token_usage,
                    "succeeded": nt.succeeded,
                    "error": nt.error,
                }
                for nt in trace.node_traces
            ],
            "total_duration_ms": trace.total_duration_ms,
            "rubric_results": trace.rubric_results,
            "verification_results": trace.verification_results,
            "human_decisions": trace.human_decisions,
            "final_confidence": trace.final_confidence,
            "published": trace.published,
            "publish_urls": trace.publish_urls,
            "metadata": trace.metadata,
        },
        default=str,
    )


async def _store_traces(traces: list[AgentTrace]) -> None:
    for trace in traces:
        await execute(
            """
            INSERT INTO agent_traces (id, org_id, workflow_id, trace_data, created_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            trace.trace_id,
            trace.org_id,
            trace.workflow_id,
            _trace_to_payload(trace),
            trace.timestamp,
        )
        for nt in trace.node_traces:
            await execute(
                """
                INSERT INTO agent_trace_nodes (
                    org_id, trace_id, workflow_id, node_name,
                    start_time, end_time, duration_ms, token_usage,
                    input_state, output_state, error, succeeded
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb, $11, $12)
                """,
                trace.org_id,
                trace.trace_id,
                trace.workflow_id,
                nt.node_name,
                nt.start_time,
                nt.end_time,
                nt.duration_ms,
                nt.token_usage,
                json.dumps(nt.input_state or {}),
                json.dumps(nt.output_state or {}),
                nt.error,
                nt.succeeded,
            )


def _dict_to_trace(data: dict) -> AgentTrace:
    node_traces = [
        NodeTrace(
            node_name=nt["node_name"],
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=nt.get("duration_ms", 0),
            error=nt.get("error"),
            token_usage=nt.get("token_usage", 0),
        )
        for nt in data.get("node_traces", [])
    ]
    return AgentTrace(
        trace_id=data.get("trace_id", ""),
        org_id=data.get("org_id", ""),
        workflow_id=data.get("workflow_id", ""),
        question=data.get("question", ""),
        question_type=data.get("question_type", "unknown"),
        source=data.get("source", "cli"),
        nodes_executed=data.get("nodes_executed", []),
        node_traces=node_traces,
        total_duration_ms=data.get("total_duration_ms", 0),
        rubric_results=data.get("rubric_results", []),
        verification_results=data.get("verification_results", []),
        human_decisions=data.get("human_decisions", []),
        final_confidence=data.get("final_confidence", 0),
        published=data.get("published", False),
        publish_urls=data.get("publish_urls", []),
    )
