"""Tests for Slack status helpers (reactions, progress)."""
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_set_assistant_status():
    from src.integrations.slack_status import set_assistant_status

    mock_client = AsyncMock()
    await set_assistant_status(mock_client, "C123", "1234.5678", "Working...")

    mock_client.assistantAssistantThreadsSetStatus.assert_called_once_with(
        channel_id="C123",
        thread_ts="1234.5678",
        status="Working...",
    )


@pytest.mark.asyncio
async def test_set_assistant_status_swallows_error():
    from src.integrations.slack_status import set_assistant_status

    mock_client = AsyncMock()
    mock_client.assistantAssistantThreadsSetStatus.side_effect = Exception(
        "not supported"
    )

    # Should not raise
    await set_assistant_status(mock_client, "C123", "1234.5678", "Working...")


@pytest.mark.asyncio
async def test_clear_assistant_status():
    from src.integrations.slack_status import clear_assistant_status

    mock_client = AsyncMock()
    await clear_assistant_status(mock_client, "C123", "1234.5678")

    mock_client.assistantAssistantThreadsSetStatus.assert_called_once_with(
        channel_id="C123",
        thread_ts="1234.5678",
        status="",
    )
