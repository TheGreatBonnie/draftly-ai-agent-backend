from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.auth import get_verified_token

router = APIRouter()


@router.get("/stats")
async def memory_stats(token: dict = Depends(get_verified_token)) -> dict:
    from src.database import fetch_all, fetch_one

    org_id = token.get("org_id")

    table_rows = await fetch_all(
        "SELECT 'support_threads' as name, COUNT(*)::int as count FROM support_threads "
        "UNION ALL SELECT 'documentation', COUNT(*)::int FROM documentation "
        "UNION ALL SELECT 'embeddings', COUNT(*)::int FROM embeddings "
        "UNION ALL SELECT 'review_sessions', COUNT(*)::int FROM review_sessions "
        "UNION ALL SELECT 'agent_memory', COUNT(*)::int FROM agent_memory "
        "UNION ALL SELECT 'audit_logs', COUNT(*)::int FROM audit_logs"
    )
    result = {row["name"]: row["count"] for row in table_rows}

    if org_id:
        platform_rows = await fetch_all(
            """
            SELECT
                COALESCE(details->>'source', 'unknown') as platform,
                COUNT(*)::int as count
            FROM audit_logs
            WHERE org_id = $1
              AND created_at > now() - interval '24 hours'
            GROUP BY platform
            ORDER BY count DESC
            """,
            org_id,
        )
        result["platform_counts"] = {
            row["platform"]: row["count"] for row in platform_rows
        }

        active = await fetch_one(
            "SELECT COUNT(*)::int as count FROM agent_workflows "
            "WHERE org_id = $1 AND status = 'running'",
            org_id,
        )
        result["active_workflows"] = active["count"] if active else 0
    else:
        result["platform_counts"] = {}
        result["active_workflows"] = 0

    return result


@router.get("/search")
async def search_memory(
    q: str = "",
    type: str = "all",
    token: dict = Depends(get_verified_token),
) -> list[dict]:
    if not q:
        return []
    from src.memory.vector_store import search_similar

    org_id = token.get("org_id")
    if not org_id:
        return []
    return await search_similar(
        org_id=org_id,
        query_text=q,
        content_type=type if type != "all" else None,
    )
