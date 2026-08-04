from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_store_reflection_returns_id():
    from src.memory.reflections import store_reflection

    with patch("src.memory.reflections.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"id": "ref-1"}
        result = await store_reflection(
            org_id="org-1",
            episode_id="ep-1",
            lesson="Prefer explicit transactions",
            confidence=0.8,
            tags=["transactions"],
        )
    assert result == "ref-1"
    sql = mock_fetch.await_args.args[0]
    assert "INSERT INTO reflections" in sql


@pytest.mark.asyncio
async def test_link_episode_reflection_inserts_memory_link():
    from src.memory.reflections import link_episode_reflection

    with patch("src.memory.reflections.execute", new_callable=AsyncMock) as mock_exec:
        await link_episode_reflection("org-1", "ep-1", "ref-1")

    sql = mock_exec.await_args.args[0]
    assert "INSERT INTO memory_links" in sql
    assert mock_exec.await_args.args[1] == "org-1"
