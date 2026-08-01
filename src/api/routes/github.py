from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.agents.runners.github_runner import run_github_pipeline
from src.api.auth import get_verified_token
from src.config import settings
from src.integrations.github_app import get_installation_token, verify_webhook_signature

logger = structlog.get_logger()

router = APIRouter()


class WebhookResponse(BaseModel):
    status: str


class LinkGitHubRequest(BaseModel):
    installation_id: int


@router.get("/install-url")
async def github_install_url(token: dict = Depends(get_verified_token)) -> dict:
    if not settings.github_app_slug:
        raise HTTPException(status_code=500, detail="GitHub App slug not configured")
    return {"install_url": f"https://github.com/apps/{settings.github_app_slug}/installations/new"}


@router.post("/link")
async def link_github(
    request: LinkGitHubRequest,
    token: dict = Depends(get_verified_token),
) -> dict:
    """Link a GitHub App installation to the current Clerk organization."""
    from src.integrations.github_app import (
        get_installation_info,
        get_installation_repositories,
        get_installation_token,
    )
    from src.memory.organizations import get_org_by_github, store_github_installation

    org_id = token.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization selected")

    # Look up installation details from GitHub API
    try:
        info = await get_installation_info(request.installation_id)
    except Exception as e:
        logger.error("github_installation_lookup_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to look up GitHub installation")

    account = info.get("account") or {}
    github_org = account.get("login")
    if not github_org:
        raise HTTPException(status_code=400, detail="Invalid installation: no account found")

    # Check if this GitHub org is already linked to a different Clerk org
    existing = await get_org_by_github(github_org)
    if existing and existing["id"] != org_id:
        raise HTTPException(
            status_code=409,
            detail=f"GitHub org '{github_org}' is already linked to another organization",
        )

    # Link: update org's github_org column
    from src.database import fetch_one

    await fetch_one(
        "UPDATE organizations SET github_org = $1 WHERE clerk_org_id = $2",
        github_org,
        org_id,
    )

    # Store the installation record
    try:
        install_token = await get_installation_token(request.installation_id)
        repos = await get_installation_repositories(install_token)
        repositories = [
            {"full_name": repo["full_name"], "id": repo["id"]}
            for repo in repos
        ]
    except Exception as e:
        logger.warning("github_repos_fetch_failed", error=str(e))
        repositories = []
    await store_github_installation(
        org_id=org_id,
        installation_id=request.installation_id,
        github_org=github_org,
        repositories=repositories,
    )

    logger.info(
        "github_linked",
        org_id=org_id,
        github_org=github_org,
        installation_id=request.installation_id,
    )
    return {"status": "linked", "github_org": github_org}


@router.get("/installations")
async def github_installations(token: dict = Depends(get_verified_token)) -> list[dict]:
    from src.memory.organizations import list_github_installations

    return await list_github_installations()


@router.get("/setup-callback")
async def github_setup_callback(
    installation_id: int | None = None,
    setup_action: str | None = None,
) -> RedirectResponse:
    if setup_action:
        logger.info(
            "github_setup_callback",
            installation_id=installation_id,
            setup_action=setup_action,
        )
    frontend_url = f"{settings.app_url}/settings"
    if installation_id:
        frontend_url += f"?github=connected&installation_id={installation_id}"
    return RedirectResponse(url=frontend_url)


@router.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks) -> WebhookResponse:
    """Receive and process GitHub webhook events."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if signature is None or not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = request.headers.get("X-GitHub-Event")

    # Handle installation events (created/deleted)
    if event_type == "installation":
        from src.memory.organizations import (
            get_org_by_github,
            remove_github_installation,
            store_github_installation,
        )

        action = payload.get("action")
        installation = payload.get("installation")
        if not installation:
            logger.warning("github_installation_malformed")
            raise HTTPException(status_code=400, detail="Missing installation in payload")

        installation_id = installation["id"]
        account = installation.get("account") or {}
        github_org = account.get("login", "unknown")

        if action == "created":
            repositories = [
                {"full_name": repo["full_name"], "id": repo["id"]}
                for repo in payload.get("repositories", [])
            ]
            org = await get_org_by_github(github_org)
            if not org:
                raise HTTPException(
                    status_code=400,
                    detail=f"Organization '{github_org}' not found. Create it via Clerk first.",
                )
            org_id = org["id"]
            await store_github_installation(
                org_id=org_id,
                installation_id=installation_id,
                github_org=github_org,
                repositories=repositories,
            )
            logger.info(
                "github_app_installed",
                installation_id=installation_id,
                org=github_org,
                repo_count=len(repositories),
            )
            return WebhookResponse(status="Installation created")

        elif action == "deleted":
            await remove_github_installation(installation_id)
            logger.info(
                "github_app_uninstalled",
                installation_id=installation_id,
                org=github_org,
            )
            return WebhookResponse(status="Installation deleted")

        return WebhookResponse(status=f"Installation {action} (unhandled)")

    # Handle issue events
    if event_type == "issues" and payload.get("action") == "opened":
        installation_id = payload["installation"]["id"]

        try:
            token = await get_installation_token(installation_id)
        except Exception as e:
            logger.error("failed_to_get_installation_token", error=str(e))
            raise HTTPException(status_code=500, detail="Failed to get installation token")

        background_tasks.add_task(run_github_pipeline, payload=payload, installation_token=token)

        logger.info(
            "github_webhook_received",
            event_type=event_type,
            action=payload.get("action"),
            repo=payload.get("repository", {}).get("full_name"),
            issue=payload.get("issue", {}).get("number"),
        )

        return WebhookResponse(status="Processing issue event")

    # Ignore other events
    logger.info("github_event_ignored", event_type=event_type)
    return WebhookResponse(status="Event ignored")
