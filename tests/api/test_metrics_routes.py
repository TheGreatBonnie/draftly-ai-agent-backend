"""Tests for GET /api/metrics/* endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_summary_returns_aggregates():
    from src.api.routes.metrics import get_summary

    expected = {"quality": {"total_episodes": 1}, "execution": {}, "product": {}}
    with patch(
        "src.api.routes.metrics.metrics_service.compute_summary",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_service:
        result = await get_summary(window_days=7, token={"org_id": "org-1"})

    assert result == expected
    mock_service.assert_awaited_once_with("org-1", window_days=7)


@pytest.mark.asyncio
async def test_get_summary_no_org():
    from src.api.routes.metrics import get_summary

    with patch(
        "src.api.routes.metrics.metrics_service.compute_summary",
        new_callable=AsyncMock,
    ) as mock_service:
        result = await get_summary(window_days=7, token={})

    assert result == {}
    mock_service.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_node_health_returns_rows():
    from src.api.routes.metrics import get_node_health

    expected = [{"node_name": "write", "runs": 5}]
    with patch(
        "src.api.routes.metrics.metrics_service.compute_node_health",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_service:
        result = await get_node_health(window_days=7, token={"org_id": "org-1"})

    assert result == expected
    mock_service.assert_awaited_once_with("org-1", window_days=7)


@pytest.mark.asyncio
async def test_get_node_health_no_org():
    from src.api.routes.metrics import get_node_health

    with patch(
        "src.api.routes.metrics.metrics_service.compute_node_health",
        new_callable=AsyncMock,
    ) as mock_service:
        result = await get_node_health(window_days=7, token={})

    assert result == []
    mock_service.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_timeseries_returns_buckets():
    from src.api.routes.metrics import get_timeseries

    expected = {"granularity": "day", "buckets": []}
    with patch(
        "src.api.routes.metrics.metrics_service.compute_timeseries",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_service:
        result = await get_timeseries(
            granularity="day", window_days=7, token={"org_id": "org-1"}
        )

    assert result == expected
    mock_service.assert_awaited_once_with("org-1", granularity="day", window_days=7)


@pytest.mark.asyncio
async def test_get_timeseries_no_org():
    from src.api.routes.metrics import get_timeseries

    with patch(
        "src.api.routes.metrics.metrics_service.compute_timeseries",
        new_callable=AsyncMock,
    ) as mock_service:
        result = await get_timeseries(
            granularity="hour", window_days=7, token={}
        )

    assert result == {"granularity": "hour", "buckets": []}
    mock_service.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_problems_returns_topics():
    from src.api.routes.metrics import get_problems

    expected = [{"topic": "how do i deploy", "count": 2}]
    with patch(
        "src.api.routes.metrics.metrics_service.compute_problems",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_service:
        result = await get_problems(
            window_days=7, limit=10, token={"org_id": "org-1"}
        )

    assert result == expected
    mock_service.assert_awaited_once_with("org-1", window_days=7, limit=10)


@pytest.mark.asyncio
async def test_get_problems_no_org():
    from src.api.routes.metrics import get_problems

    with patch(
        "src.api.routes.metrics.metrics_service.compute_problems",
        new_callable=AsyncMock,
    ) as mock_service:
        result = await get_problems(window_days=7, limit=10, token={})

    assert result == []
    mock_service.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_traces_returns_rows():
    from src.api.routes.metrics import get_traces

    expected = [{"id": "abc", "question": "How?"}]
    with patch(
        "src.api.routes.metrics.metrics_service.get_recent_traces",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_service:
        result = await get_traces(limit=20, token={"org_id": "org-1"})

    assert result == expected
    mock_service.assert_awaited_once_with("org-1", limit=20)


@pytest.mark.asyncio
async def test_get_traces_no_org():
    from src.api.routes.metrics import get_traces

    with patch(
        "src.api.routes.metrics.metrics_service.get_recent_traces",
        new_callable=AsyncMock,
    ) as mock_service:
        result = await get_traces(limit=20, token={})

    assert result == []
    mock_service.assert_not_awaited()
