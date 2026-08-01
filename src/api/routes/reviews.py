from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.auth import get_verified_token

logger = structlog.get_logger()

router = APIRouter()


class ReviewDecision(BaseModel):
    decision: str  # approve, reject, revise
    feedback: str = ""


DECISION_TO_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "revise": "needs_changes",
}


@router.get("")
async def get_all(token: dict = Depends(get_verified_token)) -> list[dict]:
    from src.memory.reviewer import get_all_reviews

    org_id = token.get("org_id")
    if not org_id:
        return []
    return await get_all_reviews(org_id=org_id)


@router.get("/pending")
async def get_pending(token: dict = Depends(get_verified_token)) -> list[dict]:
    from src.memory.reviewer import get_pending_reviews

    org_id = token.get("org_id")
    if not org_id:
        return []
    return await get_pending_reviews(org_id=org_id)


@router.post("/{review_id}/decide")
async def decide_review(
    review_id: str,
    body: ReviewDecision,
    token: dict = Depends(get_verified_token),
) -> dict:
    from src.memory.reviewer import complete_review

    await complete_review(
        review_id=review_id,
        status=DECISION_TO_STATUS.get(body.decision, body.decision),
        feedback=body.feedback,
    )

    try:
        from src.agents.runners.resume import resume_review

        await resume_review(
            review_id=review_id,
            decision=body.decision,
            feedback=body.feedback or "",
        )
    except Exception as e:
        logger.error(
            "graph_resume_failed",
            review_id=review_id,
            error=str(e),
        )

    return {"status": "ok", "decision": body.decision, "user_id": token["user_id"]}


@router.get("/{review_id}")
async def get_review(review_id: str, token: dict = Depends(get_verified_token)) -> dict:
    from src.database import fetch_one

    row = await fetch_one(
        "SELECT rs.*, rs.id::text as id, d.title, d.content, d.doc_type, d.confidence_score, "
        "d.workflow_id, "
        "st.question_summary as original_question, st.source as platform "
        "FROM review_sessions rs "
        "JOIN documentation d ON d.id = rs.doc_id "
        "LEFT JOIN support_threads st ON d.source_thread_id = st.id "
        "WHERE rs.id = $1",
        review_id,
    )
    return dict(row) if row else {"error": "not found"}
