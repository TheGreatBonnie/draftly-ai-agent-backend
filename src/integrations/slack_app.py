"""Slack Bolt app with event and action handlers."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import structlog
from slack_bolt.app.async_app import AsyncApp

from src.config import settings
from src.integrations.slack import add_reaction
from src.integrations.slack_conversation import conversation_store
from src.integrations.slack_feedback import handle_feedback
from src.integrations.slack_home import build_app_home
from src.integrations.slack_store import installation_store

bolt_logger = logging.getLogger("slack_bolt")
struct_logger = structlog.get_logger()

# Dedup guard: track recently processed message timestamps to prevent
# duplicate pipeline runs when Slack fires both app_mention and message events.
_processed_ts: set[str] = set()
_MAX_PROCESSED_TS = 500


slack_app = AsyncApp(
    signing_secret=settings.slack_signing_secret.get_secret_value(),
    installation_store=installation_store,
    installation_store_bot_only=True,
    logger=bolt_logger,
)


@slack_app.event("app_mention")
async def handle_app_mention(event: dict, context: dict, logger: Any) -> None:
    """Handle @bot mentions. Dispatches to the pipeline."""
    await _dispatch_message(event, context)


@slack_app.event("message")
async def handle_message(event: dict, context: dict, logger: Any) -> None:
    """Handle direct messages only. Channel mentions are handled by app_mention."""
    channel = event.get("channel", "")
    if not channel.startswith("D"):
        return
    await _dispatch_message(event, context)


@slack_app.event("app_home_opened")
async def handle_app_home_opened(client: Any, event: dict, logger: Any) -> None:
    """Publish App Home view when user opens the Home tab."""
    tab = event.get("tab", "")
    if tab != "home":
        return

    user_id = event.get("user", "")
    team_id = event.get("view", {}).get("team_id", "")

    team_name = ""
    if team_id:
        installation = await installation_store.async_find_installation(None, team_id)
        if installation:
            team_name = installation.team_name or ""

    view = build_app_home(team_name=team_name)
    try:
        await client.views_publish(user_id=user_id, view=view)
    except Exception:
        logger.debug("views_publish_failed")


async def _dispatch_message(event: dict, context: dict) -> None:
    """Common dispatch logic for mentions and DMs."""
    channel = event.get("channel", "")
    ts = event.get("ts", "")

    # Dedup: Slack may fire both app_mention and message for the same event
    if ts in _processed_ts:
        return
    _processed_ts.add(ts)
    if len(_processed_ts) > _MAX_PROCESSED_TS:
        _processed_ts.clear()

    thread_ts = event.get("thread_ts") or ts
    text = event.get("text", "")
    user = event.get("user", "")
    team_id = context.get("team_id", "")
    bot_user_id = context.get("bot_user_id", "")

    clean_text = text.replace(f"<@{bot_user_id}>", "").strip()
    if not clean_text:
        return

    try:
        reaction_result = await add_reaction(channel, ts, "eyes")
        if not reaction_result.get("ok"):
            struct_logger.warning(
                "slack_reaction_failed",
                error=reaction_result.get("error"),
                channel=channel,
            )
    except Exception as e:
        struct_logger.error("slack_reaction_exception", error=str(e))

    history: list[dict[str, str]] = []
    try:
        history = await conversation_store.get_history(channel, thread_ts)
    except Exception as e:
        struct_logger.warning("conversation_history_load_failed", error=str(e))

    try:
        await conversation_store.add_message(channel, thread_ts, "user", clean_text)
    except Exception as e:
        struct_logger.warning("conversation_store_save_failed", error=str(e))

    asyncio.create_task(
        _run_pipeline(team_id, channel, thread_ts, ts, clean_text, user, history)
    )
    struct_logger.info("slack_message_received", team_id=team_id, channel=channel)


async def _run_pipeline(
    team_id: str,
    channel: str,
    thread_ts: str,
    ts: str,
    text: str,
    user: str,
    message_history: list[dict[str, str]] | None = None,
) -> None:
    """Lazy import wrapper to avoid circular dependencies."""
    from src.agents.runners.slack_runner import run_slack_pipeline

    await run_slack_pipeline(
        team_id=team_id,
        channel=channel,
        thread_ts=thread_ts,
        ts=ts,
        text=text,
        user=user,
        message_history=message_history or [],
    )


STATUS_MAP = {
    "approve_review": "approved",
    "reject_review": "rejected",
    "revise_review": "needs_changes",
}

DECISION_MAP = {
    "approve_review": "approve",
    "reject_review": "reject",
    "revise_review": "revise",
}


@slack_app.action("approve_review")
async def handle_approve(ack: Any, action: dict, logger: Any) -> None:
    await ack()
    await _handle_review_action(action, "approve_review")


@slack_app.action("reject_review")
async def handle_reject(ack: Any, action: dict, logger: Any) -> None:
    await ack()
    await _handle_review_action(action, "reject_review")


@slack_app.action("revise_review")
async def handle_revise(ack: Any, action: dict, logger: Any) -> None:
    await ack()
    await _handle_review_action(action, "revise_review")


async def _handle_review_action(action: dict, action_id: str) -> None:
    """Process a review button click."""
    from src.memory.reviewer import complete_review
    from src.security.tokens import verify_review_token

    token = action.get("value", "")
    token_data = verify_review_token(token)
    if not token_data:
        return

    review_id: str = token_data.get("review_id", "")
    status = STATUS_MAP[action_id]
    decision = DECISION_MAP[action_id]

    await complete_review(review_id=review_id, status=status, feedback=None)

    try:
        from src.agents.runners.resume import resume_review

        await resume_review(review_id=review_id, decision=decision, feedback="")
    except Exception as e:
        struct_logger.error(
            "slack_review_resume_failed", review_id=review_id, error=str(e)
        )

    struct_logger.info(f"slack_review_{decision}", review_id=review_id)


@slack_app.action("draftly_feedback")
async def handle_draftly_feedback(ack: Any, action: dict, body: dict) -> None:
    await handle_feedback(ack, action, body)
