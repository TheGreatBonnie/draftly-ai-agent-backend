from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_store_memory_upserts_on_key_collision():
    from src.memory.organizational import store_memory

    with patch("src.memory.organizational.fetch_one", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"id": "mem-1"}
        first = await store_memory("org-1", "organizational", "key-1", {"v": 1})
        second = await store_memory("org-1", "organizational", "key-1", {"v": 2})

    assert first == "mem-1"
    assert second == "mem-1"
    sql = mock_fetch.await_args.args[0]
    assert "ON CONFLICT (org_id, key)" in sql


@pytest.mark.asyncio
async def test_store_memory_uses_provided_conn():
    from src.memory.organizational import store_memory

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"id": "mem-1"}
    result = await store_memory(
        "org-1", "organizational", "key-1", {"v": 1}, conn=mock_conn
    )
    assert result == "mem-1"
    mock_conn.fetchrow.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_memory_sets_last_accessed():
    from src.memory.organizational import store_memory

    with patch(
        "src.memory.organizational.fetch_one", new_callable=AsyncMock
    ) as mock_fetch, patch(
        "src.memory.organizational.fetch_one_conn", new_callable=AsyncMock
    ) as mock_fetch_conn:
        mock_fetch.return_value = {"id": "mem-1"}
        mock_fetch_conn.return_value = {"id": "mem-1"}
        await store_memory("org-1", "organizational", "key-1", {"v": 1})

    sql = mock_fetch.await_args.args[0]
    assert "last_accessed" in sql
    assert "last_accessed = now()" in sql


@pytest.mark.asyncio
async def test_store_audit_log_uses_provided_conn():
    from src.memory.organizational import store_audit_log

    mock_conn = AsyncMock()
    await store_audit_log(
        "org-1", actor="agent", action="publish_documentation", conn=mock_conn
    )
    mock_conn.execute.assert_awaited_once()
    sql = mock_conn.execute.await_args.args[0]
    assert "INSERT INTO audit_logs" in sql
