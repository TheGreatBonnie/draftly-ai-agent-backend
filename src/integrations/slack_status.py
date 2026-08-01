"""Slack assistant panel status and progress reaction helpers."""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()

PROGRESS_REACTIONS = {
    "research": "mag",
    "synthesize": "books",
    "write_docs": "pencil2",
    "ai_review": "robot_face",
    "human_review": "busts_in_silhouette",
    "complete": "white_check_mark",
}


async def set_assistant_status(
    client: Any, channel_id: str, thread_ts: str, status: str
) -> None:
    """Set the assistant panel status for a thread. Non-critical — swallows errors."""
    try:
        await client.assistantAssistantThreadsSetStatus(
            channel_id=channel_id,
            thread_ts=thread_ts,
            status=status,
        )
    except Exception:
        logger.debug("assistant_status_not_supported")


async def clear_assistant_status(client: Any, channel_id: str, thread_ts: str) -> None:
    """Clear the assistant panel status."""
    await set_assistant_status(client, channel_id, thread_ts, "")
