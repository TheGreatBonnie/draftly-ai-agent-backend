from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

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


async def create_reviewer(
    org_id: str,
    name: str,
    email: str | None = None,
    slack_user_id: str | None = None,
    discord_user_id: str | None = None,
    notify_slack: bool = True,
    notify_discord: bool = False,
    notify_email: bool = False,
    clerk_user_id: str | None = None,
) -> dict:
    """Create a new reviewer."""
    row = await fetch_one(
        """
        INSERT INTO reviewers (org_id, name, email, slack_user_id,
                               discord_user_id, notify_slack, notify_discord, notify_email,
                               clerk_user_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
        """,
        org_id,
        name,
        email,
        slack_user_id,
        discord_user_id,
        notify_slack,
        notify_discord,
        notify_email,
        clerk_user_id,
    )
    if row is None:
        raise RuntimeError("reviewer row missing after insert")
    logger.info("reviewer_created", id=row["id"], org_id=org_id, name=name)
    return _serialize_row(row)


async def get_reviewers_by_org(
    org_id: str,
    active_only: bool = True,
) -> list[dict]:
    """Get all reviewers for an organization."""
    query = """
        SELECT * FROM reviewers
        WHERE org_id = $1
    """
    if active_only:
        query += " AND is_active = true"
    query += " ORDER BY created_at DESC"

    rows = await fetch_all(query, org_id)
    return [_serialize_row(r) for r in rows]


async def get_reviewer_by_id(reviewer_id: str) -> dict | None:
    """Get a reviewer by ID."""
    row = await fetch_one(
        "SELECT * FROM reviewers WHERE id = $1",
        reviewer_id,
    )
    return _serialize_row(row) if row else None


async def update_reviewer(
    reviewer_id: str,
    **kwargs: Any,
) -> dict:
    """Update a reviewer."""
    allowed_fields = {
        "name", "email", "slack_user_id", "discord_user_id",
        "notify_slack", "notify_discord", "notify_email", "is_active",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        raise ValueError("No valid fields to update")

    set_clauses = []
    values = []
    for i, (key, value) in enumerate(updates.items(), 1):
        set_clauses.append(f"{key} = ${i}")
        values.append(value)

    values.append(reviewer_id)
    set_clause = ", ".join(set_clauses)

    row = await fetch_one(
        f"""
        UPDATE reviewers
        SET {set_clause}, updated_at = now()
        WHERE id = ${len(values)}
        RETURNING *
        """,
        *values,
    )
    if row is None:
        raise RuntimeError("reviewer row missing after update")
    logger.info("reviewer_updated", id=reviewer_id, fields=list(updates.keys()))
    return _serialize_row(row)


async def delete_reviewer(reviewer_id: str) -> bool:
    """Delete a reviewer."""
    await execute(
        "DELETE FROM reviewers WHERE id = $1",
        reviewer_id,
    )
    logger.info("reviewer_deleted", id=reviewer_id)
    return True


async def get_active_reviewer_ids(org_id: str) -> list[str]:
    """Get IDs of all active reviewers for an organization."""
    rows = await fetch_all(
        "SELECT id::text FROM reviewers WHERE org_id = $1 AND is_active = true",
        org_id,
    )
    return [str(row["id"]) for row in rows]


async def get_reviewer_by_clerk_user(org_id: str, clerk_user_id: str) -> dict | None:
    """Get a reviewer by their Clerk user ID within an org."""
    row = await fetch_one(
        "SELECT * FROM reviewers WHERE org_id = $1 AND clerk_user_id = $2",
        org_id,
        clerk_user_id,
    )
    return _serialize_row(row) if row else None
