from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from sysbot_helper.api import APIServer
from sysbot_helper.bot import Bot
from sysbot_helper.cogs.api_messages import ApiMessages


@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=Bot)
    bot.api = APIServer(bot)

    mock_channel = MagicMock()
    mock_message = MagicMock()
    mock_message.id = 12345
    mock_message.channel.id = 67890
    mock_message.content = "hello there"

    mock_channel.send = AsyncMock(return_value=mock_message)

    def get_channel(channel_id):
        if channel_id == 67890:
            return mock_channel
        return None

    bot.get_channel.side_effect = get_channel
    return bot


@pytest.mark.asyncio
async def test_api_messages_send_message_success(mock_bot):
    """Verifies that the raw body endpoint sends a message properly."""
    cog = ApiMessages(mock_bot)
    mock_bot.api.add_router(cog.router, instance=cog)
    async with TestClient(TestServer(mock_bot.api.app)) as client:
        resp = await client.post("/api/send_message/67890", data="hello there")
        assert resp.status == 200
        data = await resp.json()
        assert data["message"]["id"] == 12345
        assert data["message"]["channel_id"] == 67890
        assert data["message"]["content"] == "hello there"


@pytest.mark.asyncio
async def test_api_messages_send_message_channel_not_found(mock_bot):
    """Verifies that an invalid channel returns 404."""
    cog = ApiMessages(mock_bot)
    mock_bot.api.add_router(cog.router, instance=cog)
    async with TestClient(TestServer(mock_bot.api.app)) as client:
        resp = await client.post("/api/send_message/99999", data="hello there")
        assert resp.status == 404
        data = await resp.json()
        assert "not found" in data["error"]


@pytest.mark.asyncio
async def test_api_messages_send_message_form_success(mock_bot):
    """Verifies that the form endpoint sends a message properly."""
    cog = ApiMessages(mock_bot)
    mock_bot.api.add_router(cog.router, instance=cog)
    async with TestClient(TestServer(mock_bot.api.app)) as client:
        resp = await client.post("/api/send_message", data={"channel_id": "67890", "content": "hello there"})
        assert resp.status == 200
        data = await resp.json()
        assert data["message"]["id"] == 12345


@pytest.mark.asyncio
async def test_api_messages_send_message_form_missing_params(mock_bot):
    """Verifies that missing parameters in the form endpoint return 400 Bad Request."""
    cog = ApiMessages(mock_bot)
    mock_bot.api.add_router(cog.router, instance=cog)
    async with TestClient(TestServer(mock_bot.api.app)) as client:
        # Missing content
        resp = await client.post("/api/send_message", data={"channel_id": "67890"})
        assert resp.status == 400
        data = await resp.json()
        assert "missing or incorrect" in data["error"]
