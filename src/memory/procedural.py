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


async def create_workflow(
    org_id: str,
    thread_id: str,
    graph_state: dict,
    current_node: str = "ingest",
) -> str:
    row = await fetch_one(
        """
        INSERT INTO agent_workflows (org_id, thread_id, graph_state, current_node, status)
        VALUES ($1, $2, $3::jsonb, $4, 'running')
        RETURNING id::text
        """,
        org_id,
        thread_id,
        json.dumps(graph_state),
        current_node,
    )
    if row is None:
        raise RuntimeError("workflow row missing after insert")
    logger.info("workflow_created", id=row["id"])
    return cast(str, row["id"])


async def update_workflow(
    workflow_id: str,
    graph_state: dict | None = None,
    current_node: str | None = None,
    status: str | None = None,
    error: str | None = None,
    doc_id: str | None = None,
) -> None:
    sets = ["updated_at = now()"]
    args = []
    idx = 1

    if graph_state is not None:
        sets.append(f"graph_state = ${idx}::jsonb")
        args.append(json.dumps(graph_state))
        idx += 1
    if current_node is not None:
        sets.append(f"current_node = ${idx}")
        args.append(current_node)
        idx += 1
    if status is not None:
        sets.append(f"status = ${idx}")
        args.append(status)
        idx += 1
    if error is not None:
        sets.append(f"error = ${idx}")
        args.append(error)
        idx += 1
    if doc_id is not None:
        sets.append(f"doc_id = ${idx}")
        args.append(doc_id)
        idx += 1

    args.append(workflow_id)
    await execute(
        f"UPDATE agent_workflows SET {', '.join(sets)} WHERE id = ${idx}",
        *args,
    )


async def get_workflow(workflow_id: str) -> dict | None:
    row = await fetch_one(
        "SELECT *, id::text as id FROM agent_workflows WHERE id = $1", workflow_id
    )
    return dict(row) if row else None


async def get_workflows_by_status(org_id: str, status: str) -> list[dict]:
    rows = await fetch_all(
        """
        SELECT *, id::text as id FROM agent_workflows
        WHERE org_id = $1 AND status = $2
        ORDER BY created_at DESC
        """,
        org_id,
        status,
    )
    return [_serialize_row(r) for r in rows]
