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
async def test_store_reflection_aligns_params():
    from src.memory.reflections import store_reflection

    with patch("src.memory.reflections.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"id": "ref-1"}
        result = await store_reflection(
            org_id="org-1",
            episode_id="ep-1",
            lesson="Prefer explicit transactions",
            confidence=0.8,
            tags=["transactions", "db"],
        )

    assert result == "ref-1"
    args = mock_fetch.await_args.args
    sql = " ".join(args[0].split())
    assert (
        "org_id, episode_id, lesson, confidence, tags" in sql
    )
    assert args[1] == "org-1"
    assert args[2] == "ep-1"
    assert args[3] == "Prefer explicit transactions"
    assert args[4] == 0.8
    assert args[5] == ["transactions", "db"]


@pytest.mark.asyncio
async def test_store_reflection_defaults_tags_to_empty():
    from src.memory.reflections import store_reflection

    with patch("src.memory.reflections.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"id": "ref-1"}
        await store_reflection(
            org_id="org-1",
            episode_id="ep-1",
            lesson="Prefer explicit transactions",
            confidence=0.8,
        )

    assert mock_fetch.await_args.args[5] == []


@pytest.mark.asyncio
async def test_store_reflection_raises_when_row_missing():
    from src.memory.reflections import store_reflection

    with patch("src.memory.reflections.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = None
        with pytest.raises(RuntimeError):
            await store_reflection(
                org_id="org-1",
                episode_id="ep-1",
                lesson="Prefer explicit transactions",
                confidence=0.8,
                tags=["transactions"],
            )


@pytest.mark.asyncio
async def test_link_episode_reflection_inserts_memory_link():
    from src.memory.reflections import link_episode_reflection

    with patch("src.memory.reflections.execute", new_callable=AsyncMock) as mock_exec:
        await link_episode_reflection("org-1", "ep-1", "ref-1")

    sql = mock_exec.await_args.args[0]
    assert "INSERT INTO memory_links" in sql
    assert mock_exec.await_args.args[1] == "org-1"


@pytest.mark.asyncio
async def test_link_episode_reflection_flows_literals_and_params():
    from src.memory.reflections import link_episode_reflection

    with patch("src.memory.reflections.execute", new_callable=AsyncMock) as mock_exec:
        await link_episode_reflection("org-1", "ep-1", "ref-1")

    args = mock_exec.await_args.args
    sql = " ".join(args[0].split())
    assert "INSERT INTO memory_links" in sql
    assert "'yields_reflection'" in sql
    assert "'episode'" in sql
    assert "'reflection'" in sql
    assert args[1] == "org-1"
    assert args[2] == "ep-1"
    assert args[3] == "ref-1"
