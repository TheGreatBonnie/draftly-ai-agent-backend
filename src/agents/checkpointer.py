from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langchain_cockroachdb import AsyncCockroachDBSaver  # type: ignore[import-untyped]

from src.config import settings


@asynccontextmanager
async def create_checkpointer() -> AsyncIterator[AsyncCockroachDBSaver]:
    """Open the LangGraph checkpointer with psycopg pipeline mode disabled.

    CockroachDB allows one active portal per session; pipeline mode
    (Parse/Bind/Execute with no Sync) opens multiple portals and fails with
    "cannot perform operation sql.BindStmt while a different portal is open".
    supports_pipeline is read lazily per statement, so forcing it after
    construction is safe.
    """
    async with AsyncCockroachDBSaver.from_conn_string(
        settings.cockroachdb_url
    ) as checkpointer:
        checkpointer.supports_pipeline = False
        yield checkpointer
