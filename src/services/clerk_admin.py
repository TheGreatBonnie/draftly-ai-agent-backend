from __future__ import annotations

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()

CLERK_API_BASE = "https://api.clerk.com/v1"


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.clerk_secret_key.get_secret_value()}",
        "Content-Type": "application/json",
    }


async def list_org_members(org_id: str) -> list[dict]:
    """List all members of a Clerk organization with their roles."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CLERK_API_BASE}/organizations/{org_id}/memberships",
            headers=_auth_headers(),
            params={"limit": 100},
        )
        resp.raise_for_status()

    data = resp.json()
    members = []
    for m in data.get("data", []):
        public = m.get("public_user_data", {})
        members.append({
            "membership_id": m.get("id"),
            "user_id": public.get("user_id", ""),
            "email": public.get("identifier", ""),
            "role": m.get("role", ""),
            "role_name": m.get("role_name", ""),
        })

    logger.info("clerk_org_members_listed", org_id=org_id, count=len(members))
    return members


async def update_member_role(org_id: str, user_id: str, role: str) -> dict:
    """Update an org member's role via the Clerk API.

    Args:
        org_id: Clerk organization ID.
        user_id: Clerk user ID.
        role: Role key, e.g. "admin", "member", or "reviewer".
    """
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{CLERK_API_BASE}/organizations/{org_id}/memberships/{user_id}",
            headers=_auth_headers(),
            json={"role": role},
        )
        resp.raise_for_status()

    data = resp.json()
    logger.info(
        "clerk_member_role_updated",
        org_id=org_id,
        user_id=user_id,
        role=role,
    )
    return {
        "membership_id": data.get("id"),
        "role": data.get("role"),
        "role_name": data.get("role_name"),
    }
