from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import asyncpg  # type: ignore[import-untyped]
import structlog

from src.config import settings

logger = structlog.get_logger()

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.cockroachdb_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("cockroachdb_pool_created")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("cockroachdb_pool_closed")


async def fetch_one(query: str, *args: Any) -> dict[str, Any] | None:
    pool = await get_pool()
    rows = await pool.fetch(query, *args)
    return cast(dict[str, Any] | None, rows[0] if rows else None)


async def fetch_all(query: str, *args: Any) -> list[dict[str, Any]]:
    pool = await get_pool()
    rows = await pool.fetch(query, *args)
    return cast(list[dict[str, Any]], rows)


async def execute(query: str, *args: Any) -> str:
    pool = await get_pool()
    result = await pool.execute(query, *args)
    return cast(str, result)


async def fetch_val(query: str, *args: Any) -> Any | None:
    pool = await get_pool()
    rows = await pool.fetch(query, *args)
    return rows[0][0] if rows else None


@asynccontextmanager
async def transaction(isolation: str = "serializable") -> AsyncIterator[asyncpg.Connection]:
    """Run work on a single pooled connection inside an explicit transaction.

    CockroachDB is SERIALIZABLE by default; passing the isolation explicitly
    keeps intent clear and testable.
    """
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        async with conn.transaction(isolation=isolation):
            yield conn
    finally:
        await pool.release(conn)


async def execute_conn(conn: asyncpg.Connection, query: str, *args: Any) -> str:
    result = await conn.execute(query, *args)
    return cast(str, result)


async def fetch_one_conn(
    conn: asyncpg.Connection, query: str, *args: Any
) -> dict[str, Any] | None:
    rows = await conn.fetch(query, *args)
    return cast(dict[str, Any] | None, rows[0] if rows else None)
