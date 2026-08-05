from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.auth import get_verified_token
from src.database import fetch_all, fetch_one

router = APIRouter()


@router.get("/stats")
async def memory_stats(token: dict = Depends(get_verified_token)) -> dict:
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

        stale = await fetch_one(
            "SELECT COUNT(*)::int as count FROM agent_memory "
            "WHERE org_id = $1 AND last_accessed < now() - interval '90 days'",
            org_id,
        )
        total_mem = await fetch_one(
            "SELECT COUNT(*)::int as count FROM agent_memory WHERE org_id = $1",
            org_id,
        )
        stale_count = stale["count"] if stale else 0
        total_count = total_mem["count"] if total_mem else 0
        result["stale_memory_count"] = stale_count
        result["stale_memory_rate"] = (
            round(stale_count / total_count, 2) if total_count else 0.0
        )

        dups = await fetch_one(
            "SELECT COUNT(*)::int as count FROM ("
            "  SELECT content_id FROM embeddings "
            "  WHERE org_id = $1 AND content_id IS NOT NULL "
            "  GROUP BY content_id, content HAVING COUNT(*) > 1"
            ") t",
            org_id,
        )
        result["duplicate_embedding_groups"] = dups["count"] if dups else 0

        reflections = await fetch_one(
            "SELECT COUNT(*)::int as count, "
            "COALESCE(AVG(confidence), 0)::float as avg_confidence "
            "FROM reflections WHERE org_id = $1 AND status = 'active'",
            org_id,
        )
        result["reflections"] = {
            "count": reflections["count"] if reflections else 0,
            "avg_confidence": reflections["avg_confidence"] if reflections else 0.0,
        }

        link_rows = await fetch_all(
            "SELECT relation, COUNT(*)::int as count FROM memory_links "
            "WHERE org_id = $1 GROUP BY relation",
            org_id,
        )
        result["memory_link_counts"] = {r["relation"]: r["count"] for r in link_rows}

        resolution = await fetch_one(
            "SELECT COALESCE(AVG(quality_score), 0)::float as avg "
            "FROM episodes WHERE org_id = $1 "
            "AND created_at > now() - interval '30 days'",
            org_id,
        )
        result["resolution_proxy_avg_confidence"] = (
            resolution["avg"] if resolution else 0.0
        )
    else:
        result["platform_counts"] = {}
        result["active_workflows"] = 0
        result["stale_memory_count"] = 0
        result["stale_memory_rate"] = 0.0
        result["duplicate_embedding_groups"] = 0
        result["reflections"] = {"count": 0, "avg_confidence": 0.0}
        result["memory_link_counts"] = {}
        result["resolution_proxy_avg_confidence"] = 0.0

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
