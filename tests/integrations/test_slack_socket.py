"""Tests for Socket Mode entry point."""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_start_socket_mode_creates_handler():
    from src.integrations.slack_socket import start_socket_mode

    mock_handler = AsyncMock()
    with patch(
        "src.integrations.slack_socket.AsyncSocketModeHandler",
        return_value=mock_handler,
    ) as MockHandler, patch(
        "src.integrations.slack_socket.settings"
    ) as mock_settings:
        mock_settings.slack_app_token.get_secret_value.return_value = "xapp-test-token"

        await start_socket_mode()

        MockHandler.assert_called_once()
        mock_handler.start_async.assert_called_once()


@pytest.mark.asyncio
async def test_should_use_socket_mode_true():
    from src.integrations.slack_socket import should_use_socket_mode

    with patch("src.integrations.slack_socket.settings") as mock_settings:
        mock_settings.slack_app_token.get_secret_value.return_value = "xapp-real-token"
        assert should_use_socket_mode() is True


@pytest.mark.asyncio
async def test_should_use_socket_mode_false():
    from src.integrations.slack_socket import should_use_socket_mode

    with patch("src.integrations.slack_socket.settings") as mock_settings:
        mock_settings.slack_app_token.get_secret_value.return_value = ""
        assert should_use_socket_mode() is False
