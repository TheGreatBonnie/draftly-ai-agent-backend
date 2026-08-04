from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_store_episode_returns_id():
    from src.memory.episodes import store_episode

    with patch("src.memory.episodes.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"id": "ep-1"}
        result = await store_episode(
            org_id="org-1",
            workflow_id="w-1",
            source="slack",
            input_summary="how to deploy",
            outcome="published",
            quality_score=0.9,
        )
    assert result == "ep-1"
    sql = mock_fetch.await_args.args[0]
    assert "INSERT INTO episodes" in sql
