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
