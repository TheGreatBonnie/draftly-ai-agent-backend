from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from src.api.auth import get_verified_token
from src.database import fetch_all

router = APIRouter()


@router.get("")
async def get_activity(
    limit: int = Query(10, ge=1, le=50),
    token: dict = Depends(get_verified_token),
) -> list[dict]:
    org_id = token.get("org_id")
    if not org_id:
        return []

    rows = await fetch_all(
        """
        SELECT id, actor, actor_id, action, resource_type, resource_id,
               details, created_at
        FROM audit_logs
        WHERE org_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        org_id,
        limit,
    )

    return [_serialize_activity(r) for r in rows]


@router.get("/latest")
async def get_latest_activity(
    after: str = Query("", description="ISO timestamp — return events after this time"),
    token: dict = Depends(get_verified_token),
) -> list[dict]:
    org_id = token.get("org_id")
    if not org_id or not after:
        return []

    after_dt = datetime.fromisoformat(after)

    rows = await fetch_all(
        """
        SELECT id, actor, actor_id, action, resource_type, resource_id,
               details, created_at
        FROM audit_logs
        WHERE org_id = $1 AND created_at > $2
        ORDER BY created_at DESC
        LIMIT 20
        """,
        org_id,
        after_dt,
    )

    return [_serialize_activity(r, verbose=False) for r in rows]


@router.get("/events")
async def get_agent_events(
    limit: int = Query(50, ge=1, le=200),
    workflow_id: str | None = Query(None, description="Filter by workflow id"),
    level: str | None = Query(None, description="Filter by level (info|warning|error)"),
    after: str = Query("", description="ISO timestamp — return events after this time"),
    token: dict = Depends(get_verified_token),
) -> list[dict]:
    org_id = token.get("org_id")
    if not org_id:
        return []

    params: list[object] = [org_id]
    where = ["org_id = $1"]
    if workflow_id:
        params.append(workflow_id)
        where.append(f"workflow_id = ${len(params)}")
    if level:
        params.append(level)
        where.append(f"level = ${len(params)}")
    if after:
        params.append(datetime.fromisoformat(after))
        where.append(f"created_at > ${len(params)}")

    params.append(limit)
    rows = await fetch_all(
        f"""
        SELECT event_type, level, workflow_id, details, created_at
        FROM agent_events
        WHERE {" AND ".join(where)}
        ORDER BY created_at DESC
        LIMIT ${len(params)}
        """,
        *params,
    )
    return [_serialize_event(row) for row in rows]


@router.get("/events/summary")
async def get_event_summary(
    workflow_id: str | None = Query(None, description="Filter by workflow id"),
    token: dict = Depends(get_verified_token),
) -> dict:
    org_id = token.get("org_id")
    if not org_id:
        return {"last_1h": {}, "last_24h": {}}

    params: list[object] = [org_id]
    where = ["org_id = $1"]
    if workflow_id:
        params.append(workflow_id)
        where.append(f"workflow_id = ${len(params)}")

    def _query(interval: str) -> str:
        return f"""
            SELECT level, count(*)::int AS count
            FROM agent_events
            WHERE {" AND ".join(where)} AND created_at > now() - interval '{interval}'
            GROUP BY level
        """

    rows_1h = await fetch_all(_query("1 hour"), *params)
    rows_24h = await fetch_all(_query("24 hours"), *params)

    return {
        "last_1h": _serialize_summary(rows_1h),
        "last_24h": _serialize_summary(rows_24h),
    }


def _serialize_summary(rows: list) -> dict:
    return {row["level"]: row["count"] for row in rows}


def _serialize_event(row: dict) -> dict:
    raw = row["details"]
    if isinstance(raw, str):
        try:
            details = json.loads(raw)
        except json.JSONDecodeError:
            details = {}
    elif isinstance(raw, dict):
        details = raw
    else:
        details = {}
    return {
        "event_type": row["event_type"],
        "level": row["level"],
        "workflow_id": row.get("workflow_id"),
        "details": details if isinstance(details, dict) else {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def _serialize_activity(row: dict, verbose: bool = True) -> dict:
    raw = row["details"]
    d = raw if isinstance(raw, dict) else {}
    platform = _infer_platform(row["resource_type"], d)
    item: dict = {
        "id": str(row["id"]),
        "actor": row["actor"],
        "action": row["action"],
        "platform": platform,
        "summary": d.get("question") or d.get("title") or row["action"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
    if verbose:
        item.update(
            {
                "resource_type": row["resource_type"],
                "resource_id": str(row["resource_id"]) if row["resource_id"] else None,
                "channel": d.get("channel"),
                "source": d.get("source", platform),
                "details": d,
            }
        )
    return item


def _infer_platform(resource_type: str | None, details: dict) -> str:
    if resource_type == "support_thread":
        source = (details.get("source") or "").lower()
        if source in ("slack", "discord", "github", "cli"):
            return source
    if resource_type in ("slack_workflow", "discord_workflow", "github_workflow"):
        return resource_type.split("_")[0]
    return "system"
