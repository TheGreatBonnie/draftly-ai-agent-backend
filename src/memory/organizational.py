from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import cast

import structlog

from src.database import execute, fetch_all, fetch_one

logger = structlog.get_logger()


def _serialize_row(row: dict) -> dict:
    return {
        k: str(v) if isinstance(v, uuid.UUID)
        else v.isoformat() if isinstance(v, datetime)
        else v
        for k, v in dict(row).items()
    }


async def store_memory(
    org_id: str,
    memory_type: str,
    key: str,
    value: dict,
    source: str | None = None,
    confidence: float = 1.0,
) -> str:
    row = await fetch_one(
        """
        INSERT INTO agent_memory (org_id, memory_type, key, value, source, confidence)
        VALUES ($1, $2, $3, $4::jsonb, $5, $6)
        RETURNING id::text
        """,
        org_id,
        memory_type,
        key,
        json.dumps(value),
        source,
        confidence,
    )
    if row is None:
        raise RuntimeError("memory row missing after insert")
    logger.info("memory_stored", id=row["id"], memory_type=memory_type, key=key)
    return cast(str, row["id"])


async def search_memory(
    org_id: str,
    memory_type: str | None = None,
    key_pattern: str | None = None,
    limit: int = 10,
) -> list[dict]:
    conditions = ["org_id = $1"]
    args: list = [org_id]
    idx = 2

    if memory_type:
        conditions.append(f"memory_type = ${idx}")
        args.append(memory_type)
        idx += 1
    if key_pattern:
        conditions.append(f"key ILIKE '%' || ${idx} || '%'")
        args.append(key_pattern)
        idx += 1

    where = " AND ".join(conditions)
    rows = await fetch_all(
        f"""
        SELECT *, id::text as id FROM agent_memory
        WHERE {where}
        ORDER BY confidence DESC, created_at DESC
        LIMIT ${idx}
        """,
        *args,
        limit,
    )
    return [_serialize_row(r) for r in rows]


async def update_memory_access(memory_id: str) -> None:
    await execute("UPDATE agent_memory SET last_accessed = now() WHERE id = $1", memory_id)


async def store_audit_log(
    org_id: str,
    actor: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    actor_id: str | None = None,
) -> None:
    await execute(
        """
        INSERT INTO audit_logs
            (org_id, actor, actor_id, action, resource_type, resource_id, details)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        """,
        org_id,
        actor,
        actor_id,
        action,
        resource_type,
        resource_id,
        json.dumps(details or {}),
    )
