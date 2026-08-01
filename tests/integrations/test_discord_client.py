from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.integrations.discord import (
    edit_discord_message,
    get_or_create_dm_channel,
    send_discord_message,
    send_discord_thread_reply,
)


def _mock_response(status_code=200, json_data=None):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = str(json_data)
    resp.json.return_value = json_data or {}
    return resp


@pytest.mark.asyncio
@patch("src.integrations.discord.httpx.AsyncClient")
async def test_send_message_content_only(mock_client_cls):
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_response(200, {"id": "msg1"})
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client_cls.return_value.__aexit__.return_value = False

    result = await send_discord_message("123456", content="hello")

    mock_client.post.assert_called_once()
    payload = mock_client.post.call_args[1]["json"]
    assert payload == {"content": "hello"}
    assert result == {"id": "msg1"}


@pytest.mark.asyncio
@patch("src.integrations.discord.httpx.AsyncClient")
async def test_send_message_embed_only(mock_client_cls):
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_response(200, {"id": "msg2"})
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client_cls.return_value.__aexit__.return_value = False

    embed = {"title": "Test", "color": 49407}
    result = await send_discord_message("123456", embed=embed)

    payload = mock_client.post.call_args[1]["json"]
    assert payload == {"embeds": [embed]}
    assert result == {"id": "msg2"}


@pytest.mark.asyncio
@patch("src.integrations.discord.httpx.AsyncClient")
async def test_send_message_with_components(mock_client_cls):
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_response(201, {"id": "msg3"})
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client_cls.return_value.__aexit__.return_value = False

    components = [{"type": 1, "components": []}]
    result = await send_discord_message(
        "123456", content="review", embed={"title": "x"}, components=components
    )

    payload = mock_client.post.call_args[1]["json"]
    assert payload["content"] == "review"
    assert payload["embeds"] == [{"title": "x"}]
    assert payload["components"] == components
    assert result == {"id": "msg3"}


@pytest.mark.asyncio
@patch("src.integrations.discord.httpx.AsyncClient")
async def test_edit_message(mock_client_cls):
    mock_client = AsyncMock()
    mock_client.patch.return_value = _mock_response(200, {"id": "msg1"})
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client_cls.return_value.__aexit__.return_value = False

    embed = {"title": "Updated", "color": 3066993}
    result = await edit_discord_message("123", "msg1", embed=embed, components=[])

    mock_client.patch.assert_called_once()
    assert "/channels/123/messages/msg1" in mock_client.patch.call_args[0][0]
    payload = mock_client.patch.call_args[1]["json"]
    assert payload == {"embeds": [embed], "components": []}
    assert result == {"id": "msg1"}


@pytest.mark.asyncio
@patch("src.integrations.discord.httpx.AsyncClient")
async def test_send_thread_reply(mock_client_cls):
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_response(200, {"id": "msg4"})
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client_cls.return_value.__aexit__.return_value = False

    result = await send_discord_thread_reply("thread1", "reply text")

    payload = mock_client.post.call_args[1]["json"]
    assert payload == {"content": "reply text"}
    assert "/channels/thread1/messages" in mock_client.post.call_args[0][0]
    assert result == {"id": "msg4"}


@pytest.mark.asyncio
@patch("src.integrations.discord.httpx.AsyncClient")
async def test_send_message_logs_error_on_failure(mock_client_cls):
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_response(
        403, {"message": "Forbidden"}
    )
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client_cls.return_value.__aexit__.return_value = False

    result = await send_discord_message("123", content="test")
    assert result == {"message": "Forbidden"}


@pytest.mark.asyncio
@patch("src.integrations.discord.httpx.AsyncClient")
async def test_get_or_create_dm_channel(mock_client_cls):
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_response(200, {"id": "dm_channel_123"})
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client_cls.return_value.__aexit__.return_value = False

    result = await get_or_create_dm_channel("user_456")

    mock_client.post.assert_called_once()
    url = mock_client.post.call_args[0][0]
    assert url == "https://discord.com/api/v10/users/@me/channels"
    payload = mock_client.post.call_args[1]["json"]
    assert payload == {"recipient_id": "user_456"}
    assert result == "dm_channel_123"


@pytest.mark.asyncio
@patch("src.integrations.discord.httpx.AsyncClient")
async def test_get_or_create_dm_channel_raises_on_failure(mock_client_cls):
    mock_resp = _mock_response(400, {"message": "Bad Request"})
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=mock_resp
    )
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client_cls.return_value.__aexit__.return_value = False

    with pytest.raises(httpx.HTTPStatusError):
        await get_or_create_dm_channel("user_456")
