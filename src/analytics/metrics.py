"""ADLC §4 Monitor metric aggregations.

Pure async functions over :mod:`src.database` that compute the Agent Quality,
Execution, and Product metric families from the raw telemetry tables.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from src.database import fetch_all, fetch_one

DEFAULT_WINDOW_DAYS = 7
HIGH_ITERATION_THRESHOLD = 8


def _since(window_days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=window_days)


def _bucket_expr(granularity: str, column: str = "created_at") -> str:
    """SQL expression producing an ISO bucket key for the given granularity."""
    if granularity == "hour":
        return f"to_char(date_trunc('hour', {column}), 'YYYY-MM-DD\"T\"HH24:00:00')"
    return f"to_char(date_trunc('day', {column}), 'YYYY-MM-DD')"


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def _norm_topic(text: str) -> str:
    """Normalize a question title into a clustering key."""
    cleaned = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    return collapsed or "untitled"


async def compute_summary(org_id: str, window_days: int = DEFAULT_WINDOW_DAYS) -> dict:
    since = _since(window_days)

    episodes_row = (
        await fetch_one(
            """
            SELECT COUNT(*) AS total_episodes,
                   COUNT(*) FILTER (WHERE outcome = 'published') AS published,
                   AVG(quality_score) AS avg_confidence,
                   MAX(quality_score) AS max_confidence
            FROM episodes
            WHERE org_id = $1 AND created_at >= $2
            """,
            org_id,
            since,
        )
        or {}
    )

    reviews_row = (
        await fetch_one(
            """
            SELECT COUNT(*) AS total_review_decisions,
                   COUNT(*) FILTER (WHERE r.status = 'approved') AS approvals,
                   COUNT(*) FILTER (WHERE r.status = 'rejected') AS rejections,
                   COUNT(*) FILTER (WHERE r.status = 'needs_changes') AS needs_changes
            FROM review_sessions r
            JOIN documentation d ON d.id = r.doc_id
            WHERE d.org_id = $1 AND r.created_at >= $2
            """,
            org_id,
            since,
        )
        or {}
    )

    runs_row = (
        await fetch_one(
            """
            SELECT COUNT(*) AS total_runs,
                   MAX(jsonb_array_length(trace_data->'node_traces')) AS max_iterations,
                   COUNT(*) FILTER (
                       WHERE jsonb_array_length(trace_data->'node_traces') > $3
                   ) AS high_iteration_runs
            FROM agent_traces
            WHERE org_id = $1 AND created_at >= $2
            """,
            org_id,
            since,
            HIGH_ITERATION_THRESHOLD,
        )
        or {}
    )

    failed_runs_row = (
        await fetch_one(
            """
            SELECT COUNT(*) AS failed_runs
            FROM agent_workflows
            WHERE org_id = $1 AND status = 'failed' AND created_at >= $2
            """,
            org_id,
            since,
        )
        or {}
    )

    tool_errors_row = (
        await fetch_one(
            """
            SELECT COUNT(*) AS failed_tool_calls
            FROM agent_events
            WHERE org_id = $1 AND created_at >= $2
              AND event_type LIKE '%failed'
            """,
            org_id,
            since,
        )
        or {}
    )

    node_stats_row = (
        await fetch_one(
            """
            SELECT AVG(duration_ms) AS avg_latency_ms,
                   PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_latency_ms,
                   COALESCE(SUM(token_usage), 0) AS total_tokens,
                   COUNT(*) FILTER (WHERE succeeded = false) AS node_errors
            FROM agent_trace_nodes
            WHERE org_id = $1 AND created_at >= $2
            """,
            org_id,
            since,
        )
        or {}
    )

    docs_row = (
        await fetch_one(
            """
            SELECT COUNT(*) FILTER (WHERE status = 'draft') AS drafts,
                   COUNT(*) FILTER (WHERE version > 1) AS updates
            FROM documentation
            WHERE org_id = $1 AND created_at >= $2
            """,
            org_id,
            since,
        )
        or {}
    )

    threads_row = (
        await fetch_one(
            """
            SELECT COUNT(*) FILTER (WHERE status = 'resolved') AS resolved,
                   COUNT(*) FILTER (WHERE status = 'escalated') AS escalated
            FROM support_threads
            WHERE org_id = $1 AND created_at >= $2
            """,
            org_id,
            since,
        )
        or {}
    )

    total_episodes = int(episodes_row.get("total_episodes") or 0)
    published = int(episodes_row.get("published") or 0)
    total_review_decisions = int(reviews_row.get("total_review_decisions") or 0)
    approvals = int(reviews_row.get("approvals") or 0)
    rejections = int(reviews_row.get("rejections") or 0)
    needs_changes = int(reviews_row.get("needs_changes") or 0)
    total_runs = int(runs_row.get("total_runs") or 0)
    failed_runs = int(failed_runs_row.get("failed_runs") or 0)

    return {
        "quality": {
            "total_episodes": total_episodes,
            "published": published,
            "publish_rate": _rate(published, total_episodes),
            "avg_confidence": round(float(episodes_row.get("avg_confidence") or 0.0), 4),
            "max_confidence": round(float(episodes_row.get("max_confidence") or 0.0), 4),
            "acceptance_rate": _rate(approvals, total_review_decisions),
            "rejection_rate": _rate(rejections, total_review_decisions),
            "needs_changes_rate": _rate(needs_changes, total_review_decisions),
            "total_review_decisions": total_review_decisions,
        },
        "execution": {
            "total_runs": total_runs,
            "failed_runs": failed_runs,
            "run_failure_rate": _rate(failed_runs, total_runs),
            "failed_tool_calls": int(tool_errors_row.get("failed_tool_calls") or 0),
            "node_errors": int(node_stats_row.get("node_errors") or 0),
            "avg_latency_ms": round(float(node_stats_row.get("avg_latency_ms") or 0.0), 1),
            "p95_latency_ms": round(float(node_stats_row.get("p95_latency_ms") or 0.0), 1),
            "total_tokens": int(node_stats_row.get("total_tokens") or 0),
            "high_iteration_runs": int(runs_row.get("high_iteration_runs") or 0),
            "max_iterations": int(runs_row.get("max_iterations") or 0),
        },
        "product": {
            "drafts": int(docs_row.get("drafts") or 0),
            "updates": int(docs_row.get("updates") or 0),
            "approvals": approvals,
            "rejections": rejections,
            "resolved": int(threads_row.get("resolved") or 0),
            "escalated": int(threads_row.get("escalated") or 0),
        },
    }


async def compute_node_health(
    org_id: str, window_days: int = DEFAULT_WINDOW_DAYS
) -> list[dict]:
    since = _since(window_days)
    rows = await fetch_all(
        """
        SELECT node_name,
               COUNT(*) AS runs,
               COUNT(*) FILTER (WHERE succeeded = false) AS errors,
               AVG(duration_ms) AS avg_duration_ms,
               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_duration_ms,
               COALESCE(SUM(token_usage), 0) AS total_tokens
        FROM agent_trace_nodes
        WHERE org_id = $1 AND created_at >= $2
        GROUP BY node_name
        ORDER BY runs DESC
        """,
        org_id,
        since,
    )

    result: list[dict] = []
    for row in rows:
        runs = int(row["runs"])
        errors = int(row["errors"])
        result.append(
            {
                "node_name": row["node_name"],
                "runs": runs,
                "errors": errors,
                "error_rate": _rate(errors, runs),
                "avg_duration_ms": round(float(row["avg_duration_ms"] or 0.0), 1),
                "p95_duration_ms": round(float(row["p95_duration_ms"] or 0.0), 1),
                "total_tokens": int(row["total_tokens"]),
            }
        )
    return result


async def compute_timeseries(
    org_id: str,
    granularity: str = "day",
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict:
    since = _since(window_days)

    async def buckets(sql: str) -> list[tuple[str, float]]:
        rows = await fetch_all(sql, org_id, since)
        return [(row["bucket"], row["value"]) for row in rows]

    runs = await buckets(
        f"""
        SELECT {_bucket_expr(granularity)} AS bucket, COUNT(*) AS value
        FROM agent_traces
        WHERE org_id = $1 AND created_at >= $2
        GROUP BY bucket ORDER BY bucket
        """
    )
    latency = await buckets(
        f"""
        SELECT {_bucket_expr(granularity)} AS bucket, AVG(duration_ms) AS value
        FROM agent_trace_nodes
        WHERE org_id = $1 AND created_at >= $2
        GROUP BY bucket ORDER BY bucket
        """
    )
    tokens = await buckets(
        f"""
        SELECT {_bucket_expr(granularity)} AS bucket, COALESCE(SUM(token_usage), 0) AS value
        FROM agent_trace_nodes
        WHERE org_id = $1 AND created_at >= $2
        GROUP BY bucket ORDER BY bucket
        """
    )
    errors = await buckets(
        f"""
        SELECT {_bucket_expr(granularity)} AS bucket,
               COUNT(*) FILTER (WHERE succeeded = false) AS value
        FROM agent_trace_nodes
        WHERE org_id = $1 AND created_at >= $2
        GROUP BY bucket ORDER BY bucket
        """
    )
    drafts = await buckets(
        f"""
        SELECT {_bucket_expr(granularity)} AS bucket, COUNT(*) AS value
        FROM documentation
        WHERE org_id = $1 AND created_at >= $2
        GROUP BY bucket ORDER BY bucket
        """
    )
    approvals = await buckets(
        f"""
        SELECT {_bucket_expr(granularity, 'r.created_at')} AS bucket, COUNT(*) AS value
        FROM review_sessions r
        JOIN documentation d ON d.id = r.doc_id
        WHERE d.org_id = $1 AND r.status = 'approved' AND r.created_at >= $2
        GROUP BY bucket ORDER BY bucket
        """
    )
    rejections = await buckets(
        f"""
        SELECT {_bucket_expr(granularity, 'r.created_at')} AS bucket, COUNT(*) AS value
        FROM review_sessions r
        JOIN documentation d ON d.id = r.doc_id
        WHERE d.org_id = $1 AND r.status = 'rejected' AND r.created_at >= $2
        GROUP BY bucket ORDER BY bucket
        """
    )
    resolved = await buckets(
        f"""
        SELECT {_bucket_expr(granularity)} AS bucket, COUNT(*) AS value
        FROM support_threads
        WHERE org_id = $1 AND status = 'resolved' AND created_at >= $2
        GROUP BY bucket ORDER BY bucket
        """
    )

    count_sources: dict[str, list[tuple[str, float]]] = {
        "runs": runs,
        "errors": errors,
        "drafts": drafts,
        "approvals": approvals,
        "rejections": rejections,
        "resolved": resolved,
    }
    bucket_map: dict[str, dict[str, Any]] = {}
    for key, source in count_sources.items():
        for b, v in source:
            bucket_map.setdefault(b, {"bucket": b})[key] = int(v)
    for b, v in latency:
        bucket_map.setdefault(b, {"bucket": b})["avg_latency_ms"] = round(float(v), 1)
    for b, v in tokens:
        bucket_map.setdefault(b, {"bucket": b})["tokens"] = int(v)

    default = {
        "runs": 0,
        "avg_latency_ms": None,
        "tokens": 0,
        "drafts": 0,
        "approvals": 0,
        "rejections": 0,
        "errors": 0,
        "resolved": 0,
    }
    buckets_out = []
    for b in sorted(bucket_map):
        buckets_out.append({**default, **bucket_map[b]})
    return {"granularity": granularity, "buckets": buckets_out}


async def compute_problems(
    org_id: str,
    window_days: int = DEFAULT_WINDOW_DAYS,
    limit: int = 10,
) -> list[dict]:
    since = _since(window_days)
    rows = await fetch_all(
        """
        SELECT question_summary, status
        FROM support_threads
        WHERE org_id = $1 AND created_at >= $2
          AND question_summary IS NOT NULL AND question_summary <> ''
        """,
        org_id,
        since,
    )
    counts: dict[str, dict[str, Any]] = {}
    for row in rows:
        topic = _norm_topic(str(row["question_summary"]))
        entry = counts.setdefault(
            topic, {"count": 0, "sample_question": str(row["question_summary"])}
        )
        entry["count"] += 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1]["count"], reverse=True)
    return [{**entry, "topic": topic} for topic, entry in ranked[:limit]]


async def get_recent_traces(org_id: str, limit: int = 20) -> list[dict]:
    rows = await fetch_all(
        """
        SELECT id, workflow_id, trace_data, created_at
        FROM agent_traces
        WHERE org_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        org_id,
        limit,
    )
    result: list[dict] = []
    for row in rows:
        data = row["trace_data"]
        if isinstance(data, str):
            data = json.loads(data)
        result.append(
            {
                "id": str(row["id"]),
                "workflow_id": row["workflow_id"],
                "created_at": row["created_at"],
                "question": data.get("question", ""),
                "question_type": data.get("question_type", "unknown"),
                "source": data.get("source", ""),
                "nodes_executed": data.get("nodes_executed", []),
                "total_duration_ms": data.get("total_duration_ms", 0),
                "final_confidence": data.get("final_confidence", 0.0),
                "published": data.get("published", False),
                "rubric_results": data.get("rubric_results", []),
                "verification_results": data.get("verification_results", []),
                "human_decisions": data.get("human_decisions", []),
                "node_traces": data.get("node_traces", []),
            }
        )
    return result
