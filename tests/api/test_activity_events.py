"""Tests for GET /api/activity/events telemetry endpoint."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest


def _event_row(
    event_type: str = "ingest_hybrid_started",
    level: str = "info",
    details: object = {"question": "How?"},
    workflow_id: str | None = "wf-1",
    created_at: datetime | None = datetime(2026, 7, 31, 4, 22, 45),
) -> dict:
    return {
        "event_type": event_type,
        "level": level,
        "details": details,
        "workflow_id": workflow_id,
        "created_at": created_at,
    }


@pytest.mark.asyncio
async def test_get_agent_events_returns_rows():
    from src.api.routes.activity import get_agent_events

    mock_token = {"org_id": "org-1"}
    rows = [_event_row()]
    with patch(
        "src.api.routes.activity.fetch_all", new_callable=AsyncMock, return_value=rows
    ) as mock_fetch:
        result = await get_agent_events(
            limit=50, workflow_id=None, level=None, after="", token=mock_token
        )

    assert len(result) == 1
    assert result[0]["event_type"] == "ingest_hybrid_started"
    assert result[0]["level"] == "info"
    assert result[0]["details"] == {"question": "How?"}
    assert result[0]["workflow_id"] == "wf-1"
    assert result[0]["created_at"].startswith("2026-07-31")
    sql, org, limit = mock_fetch.await_args.args
    assert org == "org-1"
    assert "ORDER BY created_at DESC" in sql


@pytest.mark.asyncio
async def test_get_agent_events_no_org():
    from src.api.routes.activity import get_agent_events

    with patch("src.api.routes.activity.fetch_all", new_callable=AsyncMock) as mock_fetch:
        result = await get_agent_events(limit=50, token={})
    assert result == []
    mock_fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_agent_events_parses_str_details():
    from src.api.routes.activity import get_agent_events

    rows = [
        _event_row(
            details='{"model": "tensorx/deepseek-v4-flash"}',
            created_at=None,
            workflow_id=None,
        )
    ]
    with patch(
        "src.api.routes.activity.fetch_all", new_callable=AsyncMock, return_value=rows
    ):
        result = await get_agent_events(
            limit=50, workflow_id=None, level=None, after="", token={"org_id": "org-1"}
        )

    assert result[0]["details"] == {"model": "tensorx/deepseek-v4-flash"}
    assert result[0]["created_at"] is None
    assert result[0]["workflow_id"] is None


@pytest.mark.asyncio
async def test_get_agent_events_filters_by_workflow_id():
    from src.api.routes.activity import get_agent_events

    with patch(
        "src.api.routes.activity.fetch_all", new_callable=AsyncMock, return_value=[]
    ) as mock_fetch:
        await get_agent_events(
            limit=50, workflow_id="wf-9", level=None, after="", token={"org_id": "org-1"}
        )

    sql, org, wf, limit = mock_fetch.await_args.args
    assert "AND workflow_id = $2" in sql
    assert org == "org-1"
    assert wf == "wf-9"
    assert limit == 50


@pytest.mark.asyncio
async def test_get_agent_events_filters_by_level():
    from src.api.routes.activity import get_agent_events

    with patch(
        "src.api.routes.activity.fetch_all", new_callable=AsyncMock, return_value=[]
    ) as mock_fetch:
        await get_agent_events(
            limit=50, workflow_id=None, level="error", after="", token={"org_id": "org-1"}
        )

    sql, org, level, limit = mock_fetch.await_args.args
    assert "AND level = $2" in sql
    assert level == "error"
    assert limit == 50


@pytest.mark.asyncio
async def test_get_agent_events_after_cursor():
    from src.api.routes.activity import get_agent_events

    with patch(
        "src.api.routes.activity.fetch_all", new_callable=AsyncMock, return_value=[]
    ) as mock_fetch:
        await get_agent_events(
            limit=50,
            workflow_id=None,
            level=None,
            after="2026-07-31T00:00:00",
            token={"org_id": "org-1"},
        )

    sql, org, after_dt, limit = mock_fetch.await_args.args
    assert "AND created_at > $2" in sql
    assert after_dt == datetime(2026, 7, 31, 0, 0, 0)
    assert limit == 50


@pytest.mark.asyncio
async def test_get_agent_events_all_filters_combined():
    from src.api.routes.activity import get_agent_events

    with patch(
        "src.api.routes.activity.fetch_all", new_callable=AsyncMock, return_value=[]
    ) as mock_fetch:
        await get_agent_events(
            limit=10,
            workflow_id="wf-2",
            level="warning",
            after="2026-07-31T00:00:00",
            token={"org_id": "org-1"},
        )

    sql, *params = mock_fetch.await_args.args
    assert "AND workflow_id = $2" in sql
    assert "AND level = $3" in sql
    assert "AND created_at > $4" in sql
    assert params == ["org-1", "wf-2", "warning", datetime(2026, 7, 31, 0, 0, 0), 10]


@pytest.mark.asyncio
async def test_get_event_summary_aggregates_levels():
    from src.api.routes.activity import get_event_summary

    rows_1h = [
        {"level": "info", "count": 12},
        {"level": "error", "count": 1},
    ]
    rows_24h = [
        {"level": "info", "count": 40},
        {"level": "warning", "count": 3},
        {"level": "error", "count": 2},
    ]
    with patch(
        "src.api.routes.activity.fetch_all",
        new_callable=AsyncMock,
        side_effect=[rows_1h, rows_24h],
    ) as mock_fetch:
        result = await get_event_summary(token={"org_id": "org-1"})

    assert result == {
        "last_1h": {"info": 12, "error": 1},
        "last_24h": {"info": 40, "warning": 3, "error": 2},
    }
    assert mock_fetch.await_count == 2
    sql_1h = mock_fetch.await_args_list[0].args[0]
    sql_24h = mock_fetch.await_args_list[1].args[0]
    assert "interval '1 hour'" in sql_1h
    assert "interval '24 hours'" in sql_24h
    assert "GROUP BY level" in sql_1h


@pytest.mark.asyncio
async def test_get_event_summary_no_org():
    from src.api.routes.activity import get_event_summary

    with patch("src.api.routes.activity.fetch_all", new_callable=AsyncMock) as mock_fetch:
        result = await get_event_summary(token={})
    assert result == {"last_1h": {}, "last_24h": {}}
    mock_fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_event_summary_filters_by_workflow_id():
    from src.api.routes.activity import get_event_summary

    with patch(
        "src.api.routes.activity.fetch_all",
        new_callable=AsyncMock,
        side_effect=[[], []],
    ) as mock_fetch:
        await get_event_summary(workflow_id="wf-7", token={"org_id": "org-1"})

    for call in mock_fetch.await_args_list:
        sql, org, wf = call.args
        assert "AND workflow_id = $2" in sql
        assert org == "org-1"
        assert wf == "wf-7"
