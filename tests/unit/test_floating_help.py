import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from sysbot_helper.cogs.floating_help import ChannelWorker, FloatingHelp


@pytest.mark.asyncio
async def test_channel_worker_coalesces_message_bursts():
    bot = MagicMock()
    config = MagicMock()
    config.channel_activity_wait = 0.1
    config.magic_space = "⠀"
    config.check_message_history = 50
    config.skip_locked_channels = False

    cog = FloatingHelp(bot, config)
    worker = ChannelWorker(channel_id=123, cog=cog)
    worker._refresh_message = AsyncMock()

    worker.start()

    # Simulate burst of 10 rapid messages
    for _ in range(10):
        worker.notify_message()

    await asyncio.sleep(0.3)
    await worker.stop()

    # Coalescing & quiet period wait should result in exactly 1 refresh call
    assert worker._refresh_message.call_count == 1


@pytest.mark.asyncio
async def test_floating_help_cog_unload_stops_workers():
    bot = MagicMock()
    config = MagicMock()
    cog = FloatingHelp(bot, config)

    worker = ChannelWorker(channel_id=123, cog=cog)
    worker.task = MagicMock()
    worker.task.done.return_value = False

    cog.workers[123] = worker
    cog.cog_unload()

    assert worker.task.cancel.called
    assert len(cog.workers) == 0
