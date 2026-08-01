from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import structlog

from src.database import execute, fetch_all

logger = structlog.get_logger()

_FlushCallback = Callable[[], Coroutine[Any, Any, Any | None]]


@dataclass
class NodeTrace:
    node_name: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_ms: float = 0.0
    input_state: dict | None = None
    output_state: dict | None = None
    error: str | None = None


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
            json.dumps({
                "question": trace.question,
                "question_type": trace.question_type,
                "source": trace.source,
                "nodes_executed": trace.nodes_executed,
                "node_traces": [
                    {
                        "node_name": nt.node_name,
                        "duration_ms": nt.duration_ms,
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
            }, default=str),
            trace.timestamp,
        )


def _dict_to_trace(data: dict) -> AgentTrace:
    node_traces = [
        NodeTrace(
            node_name=nt["node_name"],
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=nt.get("duration_ms", 0),
            error=nt.get("error"),
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
