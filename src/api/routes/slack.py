"""Slack webhook routes — Bolt adapter passthrough."""
from __future__ import annotations

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from src.api.auth import get_verified_token
from src.config import settings
from src.integrations.slack_app import installation_store, slack_app

logger = structlog.get_logger()
router = APIRouter()
handler = AsyncSlackRequestHandler(slack_app)


class LinkSlackRequest(BaseModel):
    team_id: str


@router.post("/events")
async def slack_events(request: Request) -> Response:
    """Handle Slack Events API webhooks (message events, app_mention, etc.)."""
    return await handler.handle(request)


@router.post("/interactivity")
async def slack_interactivity(request: Request) -> Response:
    """Handle Slack interactivity webhooks (button clicks, dropdowns)."""
    return await handler.handle(request)


@router.get("/install-url")
async def slack_install_url(token: dict = Depends(get_verified_token)) -> dict:
    """Return the Slack OAuth authorization URL."""
    if not settings.slack_client_id:
        raise HTTPException(status_code=500, detail="Slack client ID not configured")

    scopes = ",".join([
        "app_mentions:read", "channels:history", "channels:read", "chat:write",
        "groups:history", "groups:read", "im:history", "im:read", "im:write",
        "reactions:write", "reactions:read", "users:read", "assistant:write",
    ])
    user_scopes = ",".join([
        "search:read", "channels:history", "channels:read", "groups:history",
        "groups:read", "im:history", "mpim:history", "users:read", "chat:write",
        "canvases:read", "canvases:write", "users:read.email",
    ])

    install_url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={settings.slack_client_id}"
        f"&scope={scopes}"
        f"&user_scope={user_scopes}"
        f"&redirect_uri={settings.slack_redirect_uri}"
    )
    return {"install_url": install_url}


@router.get("/oauth/callback")
async def slack_oauth_callback(code: str, state: str = "") -> RedirectResponse:
    """Exchange authorization code for tokens and save installation."""
    from slack_sdk.oauth.installation_store.models.installation import Installation

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "code": code,
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret.get_secret_value(),
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        logger.error("slack_oauth_failed", error=data.get("error"))
        raise HTTPException(status_code=400, detail=f"Slack OAuth failed: {data.get('error')}")

    team = data["team"]
    authed_user = data.get("authed_user", {})

    installation = Installation(
        team_id=team["id"],
        team_name=team["name"],
        bot_user_id=data.get("bot_user_id", ""),
        bot_token=data["access_token"],
        bot_scopes=data.get("scope", "").split(","),
        user_id=authed_user.get("id"),
        user_token=authed_user.get("access_token"),
        user_scopes=authed_user.get("scope", "").split(","),
        token_type="bot",
    )
    await installation_store.async_save(installation)

    logger.info("slack_oauth_success", team_id=team["id"], team_name=team["name"])

    frontend_url = f"{settings.app_url}/settings?slack=connected&team_id={team['id']}"
    return RedirectResponse(url=frontend_url)


@router.post("/link")
async def link_slack(
    request: LinkSlackRequest,
    token: dict = Depends(get_verified_token),
) -> dict:
    """Link a Slack installation to the current Clerk organization."""
    from src.memory.organizations import link_slack_installation

    org_id = token.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization selected")

    await link_slack_installation(team_id=request.team_id, org_id=org_id)
    return {"status": "linked", "team_id": request.team_id}


@router.get("/installations")
async def slack_installations(token: dict = Depends(get_verified_token)) -> list[dict]:
    from src.memory.organizations import list_slack_installations

    return await list_slack_installations()
