from __future__ import annotations

import base64
import hashlib
import hmac

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.config import settings
from src.memory.organizations import get_or_create_org_by_clerk
from src.memory.users import (
    add_user_to_org,
    create_clerk_user,
    delete_clerk_user,
    remove_user_from_org,
)

logger = structlog.get_logger()

router = APIRouter()


class WebhookResponse(BaseModel):
    status: str


def verify_svix_signature(payload: bytes, headers: dict[str, str]) -> bool:
    """Verify Svix webhook signature (used by Clerk)."""
    svix_id = headers.get("svix-id")
    svix_timestamp = headers.get("svix-timestamp")
    svix_signature = headers.get("svix-signature")

    if not svix_id or not svix_timestamp or not svix_signature:
        return False

    raw_secret = settings.clerk_signing_secret.get_secret_value()
    signing_key = base64.b64decode(raw_secret.removeprefix("whsec_"))
    to_sign = f"{svix_id}.{svix_timestamp}.{payload.decode()}"
    expected = hmac.new(signing_key, to_sign.encode(), hashlib.sha256).digest()
    expected_b64 = base64.b64encode(expected).decode()

    assert svix_signature is not None
    for sig in svix_signature.split(" "):
        if sig.startswith("v1,"):
            received = sig[3:]
            if hmac.compare_digest(received, expected_b64):
                return True
    return False


@router.post("/webhook")
async def clerk_webhook(request: Request) -> WebhookResponse:
    """Receive Clerk webhook events for user and organization lifecycle."""
    body = await request.body()
    headers = dict(request.headers)

    if not verify_svix_signature(body, headers):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json

    payload = json.loads(body)
    event_type = payload.get("type", "")
    data = payload.get("data", {})

    logger.info("clerk_webhook_received", event_type=event_type)

    # ── User events ──
    if event_type == "user.created":
        await create_clerk_user(
            clerk_user_id=data["id"],
            email=data.get("email_addresses", [{}])[0].get("email_address", ""),
            name=f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "Unknown",
            avatar_url=data.get("profile_image_url", ""),
        )

    elif event_type == "user.deleted":
        await delete_clerk_user(data["id"])

    elif event_type == "user.updated":
        await create_clerk_user(
            clerk_user_id=data["id"],
            email=data.get("email_addresses", [{}])[0].get("email_address", ""),
            name=f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "Unknown",
            avatar_url=data.get("profile_image_url", ""),
        )

    # ── Organization events ──
    elif event_type == "organization.created":
        await get_or_create_org_by_clerk(
            clerk_org_id=data["id"],
            name=data.get("name", "Unnamed Organization"),
        )

    elif event_type == "organization.deleted":
        from src.database import execute as db_execute

        await db_execute("DELETE FROM organizations WHERE clerk_org_id = $1", data["id"])
        logger.info("org_deleted_from_clerk", clerk_org_id=data["id"])

    elif event_type == "organization.updated":
        from src.database import execute as db_execute

        await db_execute(
            "UPDATE organizations SET clerk_org_name = $1 WHERE clerk_org_id = $2",
            data.get("name", ""),
            data["id"],
        )

    # ── Membership events ──
    elif event_type == "organizationMembership.created":
        await get_or_create_org_by_clerk(
            clerk_org_id=data["organization"]["id"],
            name=data["organization"].get("name", "Unnamed Organization"),
        )
        await add_user_to_org(
            clerk_user_id=data["public_user_data"]["user_id"],
            clerk_org_id=data["organization"]["id"],
            role=data.get("role", "org:member"),
        )

    elif event_type == "organizationMembership.deleted":
        await remove_user_from_org(
            clerk_user_id=data["public_user_data"]["user_id"],
            clerk_org_id=data["organization"]["id"],
        )

    elif event_type == "organizationMembership.updated":
        await get_or_create_org_by_clerk(
            clerk_org_id=data["organization"]["id"],
            name=data["organization"].get("name", "Unnamed Organization"),
        )
        await add_user_to_org(
            clerk_user_id=data["public_user_data"]["user_id"],
            clerk_org_id=data["organization"]["id"],
            role=data.get("role", "org:member"),
        )

    return WebhookResponse(status="ok")
