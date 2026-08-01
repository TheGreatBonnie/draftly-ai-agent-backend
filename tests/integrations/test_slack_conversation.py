"""Tests for CockroachDB-backed conversation store."""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_history_returns_messages():
    from src.integrations.slack_conversation import ConversationStore

    store = ConversationStore()
    mock_rows = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]

    with patch(
        "src.integrations.slack_conversation.fetch_all", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = mock_rows
        result = await store.get_history("C123", "1234.5678")

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["content"] == "hi there"
        mock_fetch.assert_called_once()


@pytest.mark.asyncio
async def test_add_message_inserts():
    from src.integrations.slack_conversation import ConversationStore

    store = ConversationStore()

    with patch(
        "src.integrations.slack_conversation.execute", new_callable=AsyncMock
    ) as mock_exec:
        await store.add_message("C123", "1234.5678", "user", "hello world")
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_deletes_old_messages():
    from src.integrations.slack_conversation import ConversationStore

    store = ConversationStore()

    with patch(
        "src.integrations.slack_conversation.execute", new_callable=AsyncMock
    ) as mock_exec:
        await store.cleanup(ttl_days=30)
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_get_history_empty():
    from src.integrations.slack_conversation import ConversationStore

    store = ConversationStore()

    with patch(
        "src.integrations.slack_conversation.fetch_all", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = []
        result = await store.get_history("C999", "9999.0000")
        assert result == []
