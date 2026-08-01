"""Slack feedback buttons for bot responses."""
from __future__ import annotations

from typing import Any

import structlog
from slack_sdk.models.blocks import FeedbackButtonsElement, SectionBlock
from slack_sdk.models.blocks.basic_components import FeedbackButtonObject, PlainTextObject

logger = structlog.get_logger()


def build_feedback_blocks() -> list[dict[str, Any]]:
    """Build Block Kit blocks with thumbs up/down feedback buttons."""
    section = SectionBlock(
        text="Was this helpful?",
        accessory=FeedbackButtonsElement(
            action_id="draftly_feedback",
            positive_button=FeedbackButtonObject(
                text=PlainTextObject(text="Yes"),
                value="good-feedback",
            ),
            negative_button=FeedbackButtonObject(
                text=PlainTextObject(text="No"),
                value="bad-feedback",
            ),
        ),
    )
    return [section.to_dict()]


async def handle_feedback(ack: Any, action: dict, body: dict) -> None:
    """Handle feedback button clicks."""
    await ack()
    value = action.get("value", "")
    user_id = body.get("user", {}).get("id", "")
    logger.info("slack_feedback_received", value=value, user_id=user_id)
