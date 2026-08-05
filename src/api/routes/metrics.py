"""ADLC §4 Monitor metrics HTTP endpoints, org-scoped via Clerk token."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.analytics import metrics as metrics_service
from src.api.auth import get_verified_token

router = APIRouter()


@router.get("/summary")
async def get_summary(
    window_days: int = Query(7, ge=1, le=90),
    token: dict = Depends(get_verified_token),
) -> dict:
    org_id = token.get("org_id")
    if not org_id:
        return {}
    return await metrics_service.compute_summary(org_id, window_days=window_days)


@router.get("/node-health")
async def get_node_health(
    window_days: int = Query(7, ge=1, le=90),
    token: dict = Depends(get_verified_token),
) -> list[dict]:
    org_id = token.get("org_id")
    if not org_id:
        return []
    return await metrics_service.compute_node_health(org_id, window_days=window_days)


@router.get("/timeseries")
async def get_timeseries(
    granularity: str = Query("day", pattern="^(day|hour)$"),
    window_days: int = Query(7, ge=1, le=90),
    token: dict = Depends(get_verified_token),
) -> dict:
    org_id = token.get("org_id")
    if not org_id:
        return {"granularity": granularity, "buckets": []}
    return await metrics_service.compute_timeseries(
        org_id, granularity=granularity, window_days=window_days
    )


@router.get("/problems")
async def get_problems(
    window_days: int = Query(7, ge=1, le=90),
    limit: int = Query(10, ge=1, le=50),
    token: dict = Depends(get_verified_token),
) -> list[dict]:
    org_id = token.get("org_id")
    if not org_id:
        return []
    return await metrics_service.compute_problems(
        org_id, window_days=window_days, limit=limit
    )


@router.get("/traces")
async def get_traces(
    limit: int = Query(20, ge=1, le=100),
    token: dict = Depends(get_verified_token),
) -> list[dict]:
    org_id = token.get("org_id")
    if not org_id:
        return []
    return await metrics_service.get_recent_traces(org_id, limit=limit)
