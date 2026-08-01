from __future__ import annotations

import structlog
from langgraph.types import interrupt

from src.agents.state import DocumentationState
from src.memory.organizational import store_audit_log
from src.memory.reviewer import create_review_session, get_pending_review_by_doc

logger = structlog.get_logger()


async def notify_reviewers(state: DocumentationState, review_id: str) -> dict:
    """Notify all active org reviewers based on their preferences."""
    from src.config import settings
    from src.integrations.discord import get_or_create_dm_channel, send_discord_message
    from src.integrations.email import send_review_notification
    from src.integrations.slack import send_slack_message
    from src.integrations.slack_blocks import build_review_notification_card
    from src.memory.reviewers import get_reviewers_by_org
    from src.security.tokens import generate_review_token

    reviewers = await get_reviewers_by_org(state["org_id"])
    title = str(state.get("draft_title", "Untitled"))
    confidence = float(state.get("confidence_score", 0))
    source = str(state.get("source", "unknown"))
    draft_content = str(state.get("draft_content", ""))

    results: dict[str, dict[str, str]] = {}

    for reviewer in reviewers:
        token = generate_review_token(reviewer["id"], review_id)
        review_page_url = f"{settings.app_url}/review/{review_id}"

        card = build_review_notification_card(
            title=title,
            source=source,
            confidence=confidence,
            dashboard_url=review_page_url,
            review_token=token,
            draft_content=draft_content,
        )

        try:
            if reviewer.get("notify_slack") and reviewer.get("slack_user_id"):
                await send_slack_message(
                    reviewer["slack_user_id"],
                    card["text"],
                    blocks=card["blocks"],
                )
                results.setdefault(reviewer["id"], {})["slack"] = "sent"

            if reviewer.get("notify_discord") and reviewer.get("discord_user_id"):
                from src.integrations.discord_blocks import build_discord_review_card

                embed_payload = build_discord_review_card(
                    title=title,
                    source=source,
                    confidence=confidence,
                    dashboard_url=review_page_url,
                    review_token=token,
                    draft_content=draft_content,
                )
                dm_channel_id = await get_or_create_dm_channel(reviewer["discord_user_id"])
                await send_discord_message(
                    dm_channel_id,
                    embed=embed_payload["embeds"][0],
                    components=embed_payload["components"],
                )
                results.setdefault(reviewer["id"], {})["discord"] = "sent"

            if reviewer.get("notify_email") and reviewer.get("email"):
                await send_review_notification(
                    to=reviewer["email"],
                    reviewer_name=reviewer["name"],
                    state=state,
                    review_id=review_id,
                    token=token,
                )
                results.setdefault(reviewer["id"], {})["email"] = "sent"

        except Exception as e:
            logger.error("notification_failed", reviewer_id=reviewer["id"], error=str(e))
            results[reviewer["id"]] = {"status": "failed", "error": str(e)}

    return results


async def human_review_node(state: DocumentationState) -> dict:
    org_id = state["org_id"]
    doc_id = state.get("doc_id", "")

    existing = await get_pending_review_by_doc(doc_id) if doc_id else None

    if existing:
        review_id = existing["id"]
        logger.info("human_review_resumed", review_id=review_id, doc_id=doc_id)
    else:
        logger.info("human_review_started", org_id=org_id, doc_id=doc_id)

        review_id = await create_review_session(
            doc_id=doc_id,
            confidence_before=state.get("confidence_score", 0),
            graph_thread_id=state.get("graph_thread_id", ""),
        )

        notification_results = await notify_reviewers(state, review_id)
        logger.info("notifications_sent", results=notification_results)

        await store_audit_log(
            org_id=org_id,
            actor="system",
            action="request_human_review",
            resource_type="documentation",
            resource_id=doc_id,
            details={
                "review_id": review_id,
                "confidence": state.get("confidence_score", 0),
            },
        )

    decision = interrupt(
        {
            "type": "documentation_review",
            "doc_id": doc_id,
            "review_id": review_id,
            "title": state.get("draft_title", ""),
            "content": state.get("draft_content", ""),
            "confidence": state.get("confidence_score", 0),
            "question": state["question"],
        }
    )

    human_decision = decision.get("decision", "reject") if isinstance(decision, dict) else "reject"
    human_feedback = decision.get("feedback", "") if isinstance(decision, dict) else ""

    logger.info("human_review_completed", decision=human_decision)

    return {
        "human_decision": human_decision,
        "human_feedback": human_feedback,
    }
