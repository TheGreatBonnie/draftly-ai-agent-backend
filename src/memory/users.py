from __future__ import annotations

from typing import cast

import structlog

from src.database import execute, fetch_one

logger = structlog.get_logger()


async def create_clerk_user(clerk_user_id: str, email: str, name: str, avatar_url: str = "") -> str:
    """Create a new user record from Clerk webhook data."""
    existing = await fetch_one(
        "SELECT id::text FROM clerk_users WHERE clerk_user_id = $1",
        clerk_user_id,
    )
    if existing:
        await execute(
            "UPDATE clerk_users SET email = $1, name = $2, avatar_url = $3, updated_at = now() "
            "WHERE clerk_user_id = $4",
            email, name, avatar_url, clerk_user_id,
        )
        return cast(str, existing["id"])

    row = await fetch_one(
        "INSERT INTO clerk_users (clerk_user_id, email, name, avatar_url) "
        "VALUES ($1, $2, $3, $4) RETURNING id::text",
        clerk_user_id, email, name, avatar_url,
    )
    logger.info("clerk_user_created", user_id=clerk_user_id)
    if row is None:
        raise RuntimeError("clerk user row missing after insert")
    return cast(str, row["id"])


async def delete_clerk_user(clerk_user_id: str) -> None:
    """Remove a user from the local DB (soft-delete or remove memberships first)."""
    await execute(
        "DELETE FROM user_organizations "
        "WHERE user_id = (SELECT id FROM clerk_users WHERE clerk_user_id = $1)",
        clerk_user_id,
    )
    await execute("DELETE FROM clerk_users WHERE clerk_user_id = $1", clerk_user_id)
    logger.info("clerk_user_deleted", user_id=clerk_user_id)


async def add_user_to_org(clerk_user_id: str, clerk_org_id: str, role: str = "org:member") -> str:
    """Link a user to an organization with a role."""
    row = await fetch_one(
        "INSERT INTO user_organizations (user_id, org_id, role) VALUES ("
        "  (SELECT id FROM clerk_users WHERE clerk_user_id = $1),"
        "  $2,"
        "  $3"
        ") ON CONFLICT (user_id, org_id) DO UPDATE SET role = $3 "
        "RETURNING id::text",
        clerk_user_id, clerk_org_id, role,
    )
    logger.info("user_added_to_org", user=clerk_user_id, org=clerk_org_id, role=role)
    if row is None:
        raise RuntimeError("user organization row missing after insert")
    return cast(str, row["id"])


async def remove_user_from_org(clerk_user_id: str, clerk_org_id: str) -> None:
    """Remove a user from an organization."""
    await execute(
        "DELETE FROM user_organizations "
        "WHERE user_id = (SELECT id FROM clerk_users WHERE clerk_user_id = $1) "
        "AND org_id = $2",
        clerk_user_id, clerk_org_id,
    )
    logger.info("user_removed_from_org", user=clerk_user_id, org=clerk_org_id)

