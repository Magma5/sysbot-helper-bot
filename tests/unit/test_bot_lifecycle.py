import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord.ext import commands

from sysbot_helper import bot_start
from sysbot_helper.api import APIRouter
from sysbot_helper.bot import Bot


@pytest.mark.asyncio
async def test_bot_close_reverse_dependency_ordering():
    bot = Bot({"token": "FAKE_TOKEN"}, load_cogs=False)

    call_order = []

    async def mock_api_stop():
        call_order.append("api.stop")

    async def mock_scheduler_stop():
        call_order.append("scheduler.stop")

    async def mock_super_close():
        call_order.append("super.close")

    async def mock_engine_dispose():
        call_order.append("engine.dispose")

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock(side_effect=mock_engine_dispose)
    bot.engine = mock_engine

    bot.api.stop = AsyncMock(side_effect=mock_api_stop)
    bot.scheduler.stop = AsyncMock(side_effect=mock_scheduler_stop)

    with patch("discord.ext.commands.Bot.close", side_effect=mock_super_close):
        await bot.close()

    assert call_order == [
        "api.stop",
        "scheduler.stop",
        "super.close",
        "engine.dispose",
    ]


@pytest.mark.asyncio
async def test_bot_close_without_database():
    bot = Bot({"token": "FAKE_TOKEN"}, load_cogs=False)
    assert bot.engine is None

    bot.api.stop = AsyncMock()
    bot.scheduler.stop = AsyncMock()

    with patch("discord.ext.commands.Bot.close", new=AsyncMock()):
        await bot.close()

    bot.api.stop.assert_awaited_once()
    bot.scheduler.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_bot_set_database_initialization():
    bot = Bot({"token": "FAKE_TOKEN"}, load_cogs=False)
    assert bot.engine is None

    with patch("sqlalchemy.ext.asyncio.create_async_engine") as mock_create_engine:
        mock_engine_instance = MagicMock()
        mock_create_engine.return_value = mock_engine_instance

        bot.set_database("sqlite+aiosqlite:///:memory:")

        assert bot.engine is mock_engine_instance
        assert "database" in bot.features
        mock_create_engine.assert_called_once_with("sqlite+aiosqlite:///:memory:")


@pytest.mark.asyncio
async def test_bot_add_cog_registers_api_router():
    bot = Bot({"token": "FAKE_TOKEN"}, load_cogs=False)
    bot.api.add_router = MagicMock()

    class CogWithRouter(commands.Cog):
        def __init__(self):
            self.router = APIRouter("/test")

    cog = CogWithRouter()
    bot.add_cog(cog)
    bot.api.add_router.assert_called_once_with(cog.router, instance=cog)


@pytest.mark.asyncio
async def test_bot_start_signal_handling_and_teardown():
    mock_bot_instance = MagicMock()
    mock_bot_instance.start = AsyncMock(side_effect=asyncio.CancelledError)
    mock_bot_instance.close = AsyncMock()

    with patch.object(Bot, "from_file", return_value=mock_bot_instance):
        with pytest.raises(asyncio.CancelledError):
            await bot_start([Path("config.yml")], load_cogs=False)

    mock_bot_instance.start.assert_awaited_once()
    mock_bot_instance.close.assert_awaited_once()
