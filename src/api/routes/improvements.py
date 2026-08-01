from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.analytics.improver import apply_improvement, update_proposal_status
from src.api.auth import get_verified_token
from src.database import fetch_all, fetch_one

router = APIRouter()


@router.get("/improvements/pending")
async def get_pending_improvements(
    org_id: str,
    token: dict = Depends(get_verified_token),
) -> dict:
    rows = await fetch_all(
        "SELECT * FROM harness_improvements "
        "WHERE org_id = $1 AND status = 'pending' "
        "ORDER BY created_at DESC",
        org_id,
    )
    return {"proposals": [dict(r) for r in rows]}


@router.get("/improvements/{proposal_id}")
async def get_improvement(
    proposal_id: str,
    token: dict = Depends(get_verified_token),
) -> dict:
    row = await fetch_one(
        "SELECT * FROM harness_improvements WHERE id = $1", proposal_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return {"proposal": dict(row)}


@router.post("/improvements/{proposal_id}/approve")
async def approve_improvement(
    proposal_id: str,
    token: dict = Depends(get_verified_token),
) -> dict:
    row = await fetch_one(
        "SELECT status FROM harness_improvements WHERE id = $1", proposal_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if row["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Proposal already {row['status']}")

    user_id = token.get("user_id", "")
    await update_proposal_status(proposal_id, "approved", reviewed_by=user_id)

    success = await apply_improvement(proposal_id)
    if success:
        return {"status": "applied", "proposal_id": proposal_id}
    return {"status": "approved_but_failed", "proposal_id": proposal_id}


@router.post("/improvements/{proposal_id}/reject")
async def reject_improvement(
    proposal_id: str,
    reason: str = "",
    token: dict = Depends(get_verified_token),
) -> dict:
    row = await fetch_one(
        "SELECT status FROM harness_improvements WHERE id = $1", proposal_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")

    user_id = token.get("user_id", "")
    await update_proposal_status(proposal_id, "rejected", reviewed_by=user_id, reason=reason)
    return {"status": "rejected", "proposal_id": proposal_id}


@router.get("/prompts/active")
async def get_active_prompts(
    org_id: str,
    token: dict = Depends(get_verified_token),
) -> dict:
    rows = await fetch_all(
        "SELECT node_name, prompt_text, version "
        "FROM prompt_versions WHERE org_id = $1 AND is_active = true",
        org_id,
    )
    return {"prompts": [dict(r) for r in rows]}


@router.get("/rubrics/active")
async def get_active_rubrics(
    org_id: str,
    token: dict = Depends(get_verified_token),
) -> dict:
    rows = await fetch_all(
        "SELECT criterion_name, criterion_text, version "
        "FROM rubric_versions WHERE org_id = $1 AND is_active = true",
        org_id,
    )
    return {"rubrics": [dict(r) for r in rows]}


@router.get("/tools/config")
async def get_tool_configs(
    org_id: str,
    token: dict = Depends(get_verified_token),
) -> dict:
    rows = await fetch_all(
        "SELECT name, description, implementation_type, config, version "
        "FROM tool_configs WHERE org_id = $1 AND enabled = true",
        org_id,
    )
    return {"tools": [dict(r) for r in rows]}


class ImprovementActionRequest(BaseModel):
    action: str


async def _execute_improvement_action(token: str, action: str) -> dict:
    from src.security.tokens import verify_review_token

    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Invalid action. Use 'approve' or 'reject'")

    payload = verify_review_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    proposal_id = payload.get("review_id")
    if not proposal_id:
        raise HTTPException(status_code=400, detail="Invalid token payload")

    row = await fetch_one(
        "SELECT status FROM harness_improvements WHERE id = $1", proposal_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if row["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Proposal already {row['status']}")

    if action == "approve":
        await update_proposal_status(proposal_id, "approved", reviewed_by="system")
        success = await apply_improvement(proposal_id)
        return {"status": "applied" if success else "approve_failed", "proposal_id": proposal_id}
    else:
        await update_proposal_status(proposal_id, "rejected", reviewed_by="system")
        return {"status": "rejected", "proposal_id": proposal_id}


@router.get("/improvements/token/{token}")
async def get_improvement_by_token(token: str) -> dict:
    from src.security.tokens import verify_review_token

    payload = verify_review_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    proposal_id = payload.get("review_id")
    if not proposal_id:
        raise HTTPException(status_code=400, detail="Invalid token payload")

    row = await fetch_one(
        "SELECT * FROM harness_improvements WHERE id = $1", proposal_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")

    return {"proposal": dict(row), "expires_at": payload["expires_at"]}


@router.post("/improvements/token/{token}/action")
async def execute_improvement_action(
    token: str, request: ImprovementActionRequest,
) -> dict:
    return await _execute_improvement_action(token, request.action)


@router.get("/improvements/token/{token}/action")
async def execute_improvement_action_get(
    token: str, action: str = "",
) -> dict:
    return await _execute_improvement_action(token, action)
