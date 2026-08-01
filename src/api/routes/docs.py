from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.auth import get_verified_token

router = APIRouter()


@router.get("/")
async def list_docs(token: dict = Depends(get_verified_token)) -> list[dict]:
    from src.database import fetch_all

    org_id = token.get("org_id")
    if not org_id:
        return []
    rows = await fetch_all(
        "SELECT d.*, d.id::text as id, st.question_summary as original_question, "
        "st.source as platform "
        "FROM documentation d "
        "LEFT JOIN support_threads st ON d.source_thread_id = st.id "
        "WHERE d.org_id = $1 ORDER BY d.created_at DESC LIMIT 50",
        org_id,
    )
    return [dict(r) for r in rows]


@router.get("/{doc_id}")
async def get_doc(doc_id: str, token: dict = Depends(get_verified_token)) -> dict:
    from src.database import fetch_one

    row = await fetch_one(
        "SELECT d.*, d.id::text as id, st.question_summary as original_question, "
        "st.source as platform "
        "FROM documentation d "
        "LEFT JOIN support_threads st ON d.source_thread_id = st.id "
        "WHERE d.id = $1",
        doc_id,
    )
    return dict(row) if row else {"error": "not found"}
