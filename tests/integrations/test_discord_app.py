"""Tests for Discord event handler."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.integrations.discord_app import _clean_discord_text, _is_bot_message, handle_message_create


def test_clean_discord_text_custom_emoji() -> None:
    """_clean_discord_text removes custom emoji."""
    text = "Hello :wave: <:smile:123456> world"
    result = _clean_discord_text(text)
    assert "<:smile:123456>" not in result
    assert "Hello" in result
    assert "world" in result


def test_clean_discord_text_collapses_whitespace() -> None:
    """_clean_discord_text collapses multiple spaces."""
    text = "Hello    world   test"
    result = _clean_discord_text(text)
    assert "Hello world test" in result


@pytest.mark.asyncio
async def test_handle_message_create_dedup() -> None:
    """handle_message_create deduplicates messages by ID."""
    from src.integrations.discord_app import _processed_ids

    _processed_ids.clear()
    data = {
        "guild_id": "g1",
        "channel_id": "ch1",
        "id": "dedup_test_123",
        "author": {"id": "user1", "bot": False},
        "content": "Hello @bot",
        "mentions": [{"id": "bot_user_id_123"}],
    }

    mock_gateway = AsyncMock()
    mock_gateway.bot_user_id = "bot_user_id_123"

    with (
        patch(
            "src.integrations.discord_app._run_pipeline", new_callable=AsyncMock
        ) as mock_pipeline,
        patch("src.integrations.discord_app.settings") as mock_settings,
        patch("src.integrations.discord_app.httpx") as mock_httpx,
        patch("src.integrations.discord_gateway.gateway", mock_gateway),
        patch(
            "src.memory.organizations.get_org_by_discord", new_callable=AsyncMock
        ) as mock_get_org,
    ):
        mock_get_org.return_value = {"discord_trigger_channels": []}
        mock_settings.discord_bot_token.get_secret_value.return_value = "fake-token"
        mock_response = AsyncMock()
        mock_response.status_code = 204
        mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(
            return_value=AsyncMock(put=AsyncMock(return_value=mock_response))
        )
        mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

        # First call should process
        await handle_message_create(data)
        import asyncio
        await asyncio.sleep(0.01)
        assert mock_pipeline.call_count == 1

        # Second call with same ID should be deduped
        await handle_message_create(data)
        await asyncio.sleep(0.01)
        assert mock_pipeline.call_count == 1

    _processed_ids.clear()
