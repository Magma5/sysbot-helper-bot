import asyncio
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from sysbot_helper.schedule import TaskScheduler, scheduled


class MockCog:
    def __init__(self):
        self.execution_count = 0

    @scheduled("*/10 * * * * *", single_instance=True)
    async def slow_task(self):
        self.execution_count += 1
        await asyncio.sleep(0.2)

    @scheduled("*/10 * * * * *", single_instance=False)
    async def normal_task(self):
        self.execution_count += 1


@pytest.mark.asyncio
async def test_single_instance_guard_skips_overlapping_ticks():
    bot = MagicMock()
    bot.now.return_value = datetime(2026, 8, 8, 12, 0, 10)
    scheduler = TaskScheduler(bot)
    cog = MockCog()
    scheduler.register_cog_tasks(cog)

    task_list = scheduler.tasks["MockCog"]
    slow_scheduled_task = next(task for c, task in task_list if task.callback.__name__ == "slow_task")

    # Start first invocation
    dt1 = datetime(2026, 8, 8, 12, 0, 10)
    task1 = asyncio.create_task(slow_scheduled_task.try_invoke(cog, dt1))
    await asyncio.sleep(0.01)

    assert slow_scheduled_task.is_running is True

    # Immediate second tick with different timestamp while task1 is running
    dt2 = datetime(2026, 8, 8, 12, 0, 20)
    await slow_scheduled_task.try_invoke(cog, dt2)

    # Execution count should still be 1 because guard skipped second tick
    assert cog.execution_count == 1

    await task1
    assert slow_scheduled_task.is_running is False
    assert cog.execution_count == 1


@pytest.mark.asyncio
async def test_unregister_cog_tasks_cancels_running_tasks():
    bot = MagicMock()
    scheduler = TaskScheduler(bot)
    cog = MockCog()
    scheduler.register_cog_tasks(cog)

    task_list = scheduler.tasks["MockCog"]
    slow_scheduled_task = next(task for c, task in task_list if task.callback.__name__ == "slow_task")

    dt1 = datetime(2026, 8, 8, 12, 0, 10)
    bg_task = asyncio.create_task(slow_scheduled_task.try_invoke(cog, dt1))
    slow_scheduled_task._active_task = bg_task
    await asyncio.sleep(0.01)

    scheduler.unregister_cog_tasks("MockCog")

    assert "MockCog" not in scheduler.tasks
    assert bg_task.cancelled() or bg_task.done()
