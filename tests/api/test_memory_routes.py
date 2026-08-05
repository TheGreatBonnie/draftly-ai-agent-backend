from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_memory_stats_includes_quality_metrics():
    from src.api.routes.memory import memory_stats

    table_rows = [
        {"name": "support_threads", "count": 3},
        {"name": "documentation", "count": 2},
        {"name": "embeddings", "count": 10},
        {"name": "review_sessions", "count": 1},
        {"name": "agent_memory", "count": 4},
        {"name": "audit_logs", "count": 5},
    ]
    with patch("src.api.routes.memory.fetch_all", new_callable=AsyncMock) as mock_all, patch(
        "src.api.routes.memory.fetch_one", new_callable=AsyncMock
    ) as mock_one:
        async def _fetch_all(sql, *args):
            if "memory_links" in sql:
                return [
                    {"relation": "yields_reflection", "count": 3},
                ]
            if "platform_counts" in sql or "audit_logs" in sql and "GROUP BY" in sql:
                return []
            return table_rows

        async def _fetch_one(sql, *args):
            if "agent_memory" in sql and "last_accessed" in sql:
                return {"count": 1}
            if "agent_memory" in sql:
                return {"count": 4}
            if "content_id" in sql:
                return {"count": 2}
            if "reflections" in sql:
                return {"count": 2, "avg_confidence": 0.7}
            if "episodes" in sql:
                return {"avg": 0.8}
            if "agent_workflows" in sql:
                return {"count": 0}
            return None

        mock_all.side_effect = _fetch_all
        mock_one.side_effect = _fetch_one

        result = await memory_stats(token={"org_id": "org-1"})

    assert result["stale_memory_count"] == 1
    assert result["stale_memory_rate"] == 0.25
    assert result["duplicate_embedding_groups"] == 2
    assert result["reflections"] == {"count": 2, "avg_confidence": 0.7}
    assert result["memory_link_counts"] == {"yields_reflection": 3}
    assert result["resolution_proxy_avg_confidence"] == 0.8


@pytest.mark.asyncio
async def test_memory_stats_no_org_returns_neutral_defaults():
    from src.api.routes.memory import memory_stats

    table_rows = [
        {"name": "support_threads", "count": 0},
        {"name": "documentation", "count": 0},
        {"name": "embeddings", "count": 0},
        {"name": "review_sessions", "count": 0},
        {"name": "agent_memory", "count": 0},
        {"name": "audit_logs", "count": 0},
    ]
    with patch("src.api.routes.memory.fetch_all", new_callable=AsyncMock) as mock_all:
        mock_all.return_value = table_rows
        result = await memory_stats(token={})

    assert result["stale_memory_count"] == 0
    assert result["stale_memory_rate"] == 0.0
    assert result["duplicate_embedding_groups"] == 0
    assert result["reflections"] == {"count": 0, "avg_confidence": 0.0}
    assert result["memory_link_counts"] == {}
    assert result["resolution_proxy_avg_confidence"] == 0.0
    assert result["active_workflows"] == 0
    assert result["platform_counts"] == {}


@pytest.mark.asyncio
async def test_memory_stats_zero_total_mem_returns_zero_rate():
    from src.api.routes.memory import memory_stats

    table_rows = [
        {"name": "support_threads", "count": 0},
        {"name": "documentation", "count": 0},
        {"name": "embeddings", "count": 0},
        {"name": "review_sessions", "count": 0},
        {"name": "agent_memory", "count": 0},
        {"name": "audit_logs", "count": 0},
    ]
    with patch("src.api.routes.memory.fetch_all", new_callable=AsyncMock) as mock_all, patch(
        "src.api.routes.memory.fetch_one", new_callable=AsyncMock
    ) as mock_one:
        async def _fetch_all(sql, *args):
            if "memory_links" in sql:
                return []
            if "GROUP BY" in sql:
                return []
            return table_rows

        async def _fetch_one(sql, *args):
            if "agent_memory" in sql and "last_accessed" in sql:
                return {"count": 0}
            if "agent_memory" in sql:
                return {"count": 0}
            if "content_id" in sql:
                return {"count": 0}
            if "reflections" in sql:
                return {"count": 0, "avg_confidence": 0}
            if "episodes" in sql:
                return {"avg": 0}
            if "agent_workflows" in sql:
                return {"count": 0}
            return None

        mock_all.side_effect = _fetch_all
        mock_one.side_effect = _fetch_one

        result = await memory_stats(token={"org_id": "org-1"})

    assert result["stale_memory_count"] == 0
    assert result["stale_memory_rate"] == 0.0


@pytest.mark.asyncio
async def test_memory_versions_returns_ordered_history():
    from src.api.routes.memory import memory_versions

    rows = [
        {"version": 1, "value": {"v": 1}, "source": "slack",
         "confidence": 1.0, "superseded_at": "2026-08-05T00:00:00Z"},
        {"version": 2, "value": {"v": 2}, "source": "email",
         "confidence": 0.9, "superseded_at": "2026-08-05T01:00:00Z"},
    ]
    with patch(
        "src.api.routes.memory.fetch_all", new_callable=AsyncMock, return_value=rows
    ) as mock_all:
        result = await memory_versions(key="key-1", token={"org_id": "org-1"})

    assert result == rows
    sql = " ".join(mock_all.await_args.args[0].split())
    assert "agent_memory_versions v" in sql
    assert "ON m.id = v.memory_id" in sql
    assert "m.org_id = $1 AND m.key = $2" in sql
    assert "ORDER BY v.version ASC" in sql


@pytest.mark.asyncio
async def test_memory_versions_returns_empty_without_key_or_org():
    from src.api.routes.memory import memory_versions

    with patch("src.api.routes.memory.fetch_all", new_callable=AsyncMock) as mock_all:
        assert await memory_versions(key="", token={"org_id": "org-1"}) == []
        assert await memory_versions(key="key-1", token={}) == []

    mock_all.assert_not_awaited()
