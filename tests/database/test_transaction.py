from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database import transaction


@pytest.mark.asyncio
async def test_transaction_yields_conn_and_releases_on_error():
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_pool.release = AsyncMock()

    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=None)
    mock_tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction.return_value = mock_tx

    with patch("src.database.get_pool", new_callable=AsyncMock, return_value=mock_pool):
        with pytest.raises(RuntimeError):
            async with transaction() as conn:
                assert conn is mock_conn
                raise RuntimeError("boom")

    mock_pool.acquire.assert_awaited_once()
    mock_conn.transaction.assert_called_once_with(isolation="serializable")
    mock_pool.release.assert_awaited_once_with(mock_conn)


@pytest.mark.asyncio
async def test_execute_conn_runs_on_conn():
    from src.database import execute_conn

    mock_conn = AsyncMock()
    await execute_conn(mock_conn, "UPDATE t SET x = $1", 5)
    mock_conn.execute.assert_awaited_once_with("UPDATE t SET x = $1", 5)


@pytest.mark.asyncio
async def test_fetch_one_conn_runs_on_conn():
    from src.database import fetch_one_conn

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [{"id": "1"}]
    row = await fetch_one_conn(mock_conn, "SELECT * FROM t")
    assert row == {"id": "1"}
    mock_conn.fetch.assert_awaited_once_with("SELECT * FROM t")
    mock_conn.fetchrow.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_one_conn_empty_returns_none():
    from src.database import fetch_one_conn

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []
    assert await fetch_one_conn(mock_conn, "SELECT * FROM t") is None


@pytest.mark.asyncio
async def test_fetch_one_returns_none_when_empty():
    from src.database import fetch_one

    mock_pool = AsyncMock()
    mock_pool.fetch.return_value = []
    with patch("src.database.get_pool", new_callable=AsyncMock, return_value=mock_pool):
        assert await fetch_one("SELECT * FROM t") is None


@pytest.mark.asyncio
async def test_fetch_val_returns_first_column_of_first_row():
    from src.database import fetch_val

    row = MagicMock()
    row.__getitem__.return_value = 42
    mock_pool = AsyncMock()
    mock_pool.fetch.return_value = [row]
    with patch("src.database.get_pool", new_callable=AsyncMock, return_value=mock_pool):
        assert await fetch_val("SELECT col FROM t") == 42
