"""Tests for src.analytics.metrics — ADLC §4 Monitor aggregations."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.analytics import metrics as metrics_module


@pytest.mark.asyncio
async def test_compute_summary_aggregates_families():
    side_effect = [
        {
            "total_episodes": 10,
            "published": 4,
            "avg_confidence": 0.72,
            "max_confidence": 0.95,
        },
        {
            "total_review_decisions": 8,
            "approvals": 5,
            "rejections": 2,
            "needs_changes": 1,
        },
        {"total_runs": 12, "max_iterations": 9, "high_iteration_runs": 2},
        {"failed_runs": 1},
        {"failed_tool_calls": 3},
        {
            "avg_latency_ms": 150.0,
            "p95_latency_ms": 400.0,
            "total_tokens": 5000,
            "node_errors": 2,
        },
        {"drafts": 3, "updates": 2},
        {"resolved": 6, "escalated": 2},
    ]
    with patch(
        "src.analytics.metrics.fetch_one", new_callable=AsyncMock, side_effect=side_effect
    ) as mock_fetch_one:
        result = await metrics_module.compute_summary("org-1", window_days=7)

    assert mock_fetch_one.await_count == 8
    quality = result["quality"]
    assert quality["total_episodes"] == 10
    assert quality["published"] == 4
    assert quality["publish_rate"] == 0.4
    assert quality["avg_confidence"] == 0.72
    assert quality["max_confidence"] == 0.95
    assert quality["acceptance_rate"] == 0.625
    assert quality["rejection_rate"] == 0.25
    assert quality["needs_changes_rate"] == 0.125
    assert quality["total_review_decisions"] == 8

    execution = result["execution"]
    assert execution["total_runs"] == 12
    assert execution["failed_runs"] == 1
    assert execution["run_failure_rate"] == 0.0833
    assert execution["failed_tool_calls"] == 3
    assert execution["node_errors"] == 2
    assert execution["avg_latency_ms"] == 150.0
    assert execution["p95_latency_ms"] == 400.0
    assert execution["total_tokens"] == 5000
    assert execution["high_iteration_runs"] == 2
    assert execution["max_iterations"] == 9

    product = result["product"]
    assert product["drafts"] == 3
    assert product["updates"] == 2
    assert product["approvals"] == 5
    assert product["rejections"] == 2
    assert product["resolved"] == 6
    assert product["escalated"] == 2


@pytest.mark.asyncio
async def test_compute_summary_empty_rows():
    with patch(
        "src.analytics.metrics.fetch_one", new_callable=AsyncMock, side_effect=[None] * 8
    ):
        result = await metrics_module.compute_summary("org-1")

    assert result["quality"]["publish_rate"] == 0.0
    assert result["execution"]["run_failure_rate"] == 0.0
    assert result["product"]["resolved"] == 0


@pytest.mark.asyncio
async def test_compute_node_health():
    rows = [
        {
            "node_name": "write",
            "runs": 5,
            "errors": 1,
            "avg_duration_ms": 100.0,
            "p95_duration_ms": 200.0,
            "total_tokens": 1000,
        },
        {
            "node_name": "review",
            "runs": 3,
            "errors": 0,
            "avg_duration_ms": 50.0,
            "p95_duration_ms": 60.0,
            "total_tokens": 500,
        },
    ]
    with patch(
        "src.analytics.metrics.fetch_all", new_callable=AsyncMock, return_value=rows
    ):
        result = await metrics_module.compute_node_health("org-1")

    assert [r["node_name"] for r in result] == ["write", "review"]
    assert result[0]["error_rate"] == 0.2
    assert result[0]["avg_duration_ms"] == 100.0
    assert result[0]["total_tokens"] == 1000
    assert result[1]["error_rate"] == 0.0


@pytest.mark.asyncio
async def test_compute_timeseries_merges_buckets():
    side_effect = [
        [{"bucket": "2026-08-01", "value": 2}, {"bucket": "2026-08-02", "value": 3}],
        [{"bucket": "2026-08-01", "value": 150.0}],
        [{"bucket": "2026-08-01", "value": 1000}, {"bucket": "2026-08-02", "value": 500}],
        [{"bucket": "2026-08-02", "value": 1}],
        [{"bucket": "2026-08-01", "value": 1}],
        [{"bucket": "2026-08-01", "value": 2}],
        [{"bucket": "2026-08-01", "value": 1}],
        [{"bucket": "2026-08-01", "value": 3}],
    ]
    with patch(
        "src.analytics.metrics.fetch_all", new_callable=AsyncMock, side_effect=side_effect
    ) as mock_fetch_all:
        result = await metrics_module.compute_timeseries("org-1", granularity="day")

    assert mock_fetch_all.await_count == 8
    assert result["granularity"] == "day"
    buckets = result["buckets"]
    assert len(buckets) == 2
    first = buckets[0]
    assert first["bucket"] == "2026-08-01"
    assert first["runs"] == 2
    assert first["avg_latency_ms"] == 150.0
    assert first["tokens"] == 1000
    assert first["errors"] == 0
    assert first["drafts"] == 1
    assert first["approvals"] == 2
    assert first["rejections"] == 1
    assert first["resolved"] == 3
    second = buckets[1]
    assert second["bucket"] == "2026-08-02"
    assert second["runs"] == 3
    assert second["avg_latency_ms"] is None
    assert second["tokens"] == 500
    assert second["errors"] == 1


@pytest.mark.asyncio
async def test_compute_timeseries_empty():
    with patch(
        "src.analytics.metrics.fetch_all", new_callable=AsyncMock, side_effect=[[]] * 8
    ):
        result = await metrics_module.compute_timeseries("org-1")

    assert result == {"granularity": "day", "buckets": []}


@pytest.mark.asyncio
async def test_compute_problems_groups_normalized_topics():
    rows = [
        {"question_summary": "How do I deploy?", "status": "resolved"},
        {"question_summary": "how do i deploy?", "status": "resolved"},
    ]
    with patch(
        "src.analytics.metrics.fetch_all", new_callable=AsyncMock, return_value=rows
    ):
        result = await metrics_module.compute_problems("org-1")

    assert len(result) == 1
    assert result[0]["count"] == 2
    assert result[0]["topic"] == "how do i deploy"


@pytest.mark.asyncio
async def test_get_recent_traces_parses_jsonb():
    trace_data = (
        '{"question": "How?", "question_type": "moderate", "source": "cli", '
        '"nodes_executed": ["write"], "total_duration_ms": 500, '
        '"final_confidence": 0.8, "published": true, "rubric_results": [], '
        '"verification_results": [], "human_decisions": [], "node_traces": []}'
    )
    rows = [
        {
            "id": "abc-123",
            "workflow_id": "wf-1",
            "trace_data": trace_data,
            "created_at": datetime(2026, 8, 1, 4, 0, 0),
        }
    ]
    with patch(
        "src.analytics.metrics.fetch_all", new_callable=AsyncMock, return_value=rows
    ):
        result = await metrics_module.get_recent_traces("org-1", limit=5)

    assert len(result) == 1
    row = result[0]
    assert row["id"] == "abc-123"
    assert row["workflow_id"] == "wf-1"
    assert row["question"] == "How?"
    assert row["question_type"] == "moderate"
    assert row["final_confidence"] == 0.8
    assert row["published"] is True
    assert row["nodes_executed"] == ["write"]
