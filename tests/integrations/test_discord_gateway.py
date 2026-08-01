"""Tests for Discord Gateway WebSocket client."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.discord_gateway import DiscordGateway


def test_clean_discord_text_removes_mentions() -> None:
    """_clean_discord_text strips @mentions, #channels, and @everyone."""
    from src.integrations.discord_app import _clean_discord_text

    text = "<@123456> <@!789012> <#345678> @everyone Hello"
    result = _clean_discord_text(text)
    assert "<@" not in result
    assert "<#" not in result
    assert "@everyone" not in result
    assert "Hello" in result


def test_is_bot_message_true_for_bots() -> None:
    """_is_bot_message returns True when author.bot is True."""
    from src.integrations.discord_app import _is_bot_message

    assert _is_bot_message("bot123", True) is True


def test_is_bot_message_false_for_users() -> None:
    """_is_bot_message returns False for regular users."""
    from src.integrations.discord_app import _is_bot_message

    assert _is_bot_message("user123", False) is False


@pytest.mark.asyncio
async def test_handle_message_create_skips_bots() -> None:
    """handle_message_create ignores messages from bots."""
    from src.integrations.discord_app import handle_message_create

    data = {
        "guild_id": "g1",
        "channel_id": "ch1",
        "id": "msg1",
        "author": {"id": "bot1", "bot": True},
        "content": "Hello",
    }
    with patch(
        "src.integrations.discord_app._run_pipeline", new_callable=AsyncMock
    ) as mock_pipeline:
        await handle_message_create(data)
        mock_pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_create_skips_empty_text() -> None:
    """handle_message_create ignores messages with no content after cleaning."""
    from src.integrations.discord_app import handle_message_create

    data = {
        "guild_id": "g1",
        "channel_id": "ch1",
        "id": "msg2",
        "author": {"id": "user1", "bot": False},
        "content": "<@123456>",
    }
    with patch(
        "src.integrations.discord_app._run_pipeline", new_callable=AsyncMock
    ) as mock_pipeline:
        await handle_message_create(data)
        mock_pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_create_skips_dms() -> None:
    """handle_message_create ignores DMs (no guild_id)."""
    from src.integrations.discord_app import handle_message_create

    data = {
        "guild_id": "",
        "channel_id": "dm1",
        "id": "msg3",
        "author": {"id": "user1", "bot": False},
        "content": "Hello",
    }
    with patch(
        "src.integrations.discord_app._run_pipeline", new_callable=AsyncMock
    ) as mock_pipeline:
        await handle_message_create(data)
        mock_pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_create_dispatches_pipeline() -> None:
    """handle_message_create dispatches valid messages to the pipeline."""
    from src.integrations.discord_app import handle_message_create

    data = {
        "guild_id": "g1",
        "channel_id": "ch1",
        "id": "msg4",
        "author": {"id": "user1", "bot": False},
        "content": "How do I reset my password? @bot",
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

        await handle_message_create(data)

        # Wait for the asyncio.create_task to complete
        import asyncio
        await asyncio.sleep(0.01)

        mock_pipeline.assert_called_once()


def test_gateway_init() -> None:
    """DiscordGateway initializes with default values."""
    gw = DiscordGateway()
    assert gw._ws is None
    assert gw._sequence is None
    assert gw._session_id is None
    assert gw._running is False
