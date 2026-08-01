from __future__ import annotations

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
    row = await pool.fetchrow(query, *args)
    return cast(dict[str, Any] | None, row)


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
    return await pool.fetchval(query, *args)
