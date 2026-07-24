from unittest.mock import MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer
from sysbot_helper.api import APIServer
from sysbot_helper.bot import Bot
from sysbot_helper.cogs.api_health import ApiHealth


@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=Bot)
    bot.api = APIServer(bot)
    return bot


@pytest.mark.asyncio
async def test_api_health_hello(mock_bot):
    """Verifies that the /hello endpoint returns 'hello, world!'."""
    cog = ApiHealth(mock_bot)
    mock_bot.api.add_router(cog.router, instance=cog)
    async with TestClient(TestServer(mock_bot.api.app)) as client:
        resp = await client.get("/hello")
        assert resp.status == 200
        text = await resp.text()
        assert text == "hello, world!\n"


@pytest.mark.asyncio
async def test_api_health_healthcheck(mock_bot):
    """Verifies that the /healthcheck endpoint returns 'OK'."""
    cog = ApiHealth(mock_bot)
    mock_bot.api.add_router(cog.router, instance=cog)
    async with TestClient(TestServer(mock_bot.api.app)) as client:
        resp = await client.get("/healthcheck")
        assert resp.status == 200
        text = await resp.text()
        assert text == "OK"
