"""CockroachDB-backed conversation store for Slack thread context."""
from __future__ import annotations

import structlog

from src.database import execute, fetch_all

logger = structlog.get_logger()


class ConversationStore:
    """Stores and retrieves conversation history per (channel_id, thread_ts)."""

    async def get_history(
        self, channel_id: str, thread_ts: str, limit: int = 20
    ) -> list[dict[str, str]]:
        """Return conversation history for a thread, oldest first."""
        rows = await fetch_all(
            """SELECT role, content FROM slack_conversations
               WHERE channel_id = $1 AND thread_ts = $2
               ORDER BY created_at ASC LIMIT $3""",
            channel_id,
            thread_ts,
            limit,
        )
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    async def add_message(
        self, channel_id: str, thread_ts: str, role: str, content: str
    ) -> None:
        """Store a single message in the conversation."""
        await execute(
            """INSERT INTO slack_conversations (channel_id, thread_ts, role, content)
               VALUES ($1, $2, $3, $4)""",
            channel_id,
            thread_ts,
            role,
            content,
        )
        logger.debug(
            "conversation_message_stored",
            channel_id=channel_id,
            thread_ts=thread_ts,
            role=role,
        )

    async def cleanup(self, ttl_days: int = 30) -> None:
        """Delete conversation messages older than ttl_days."""
        await execute(
            """DELETE FROM slack_conversations
               WHERE created_at < now() - ($1::INT || ' days')::INTERVAL""",
            ttl_days,
        )
        logger.info("conversation_cleanup_completed", ttl_days=ttl_days)


conversation_store = ConversationStore()
