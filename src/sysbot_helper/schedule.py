import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from .cron import CronExpression

log = logging.getLogger(__name__)


def scheduled(*args, **kwargs):
    """Decorator for making a scheduled task from a callback function."""

    def decorator(func):
        task = ScheduledTask(*args, callback=func, **kwargs)
        return task

    return decorator


class ScheduledTask:
    """Represents a scheduled task with associated cron expression schedules."""

    def __init__(self, *cron_expr: str, callback: Any, on_ready: bool = False) -> None:
        self.raw_schedules = cron_expr
        self.callback = callback
        self.on_ready = on_ready
        self.cron_schedules: list[CronExpression] = []

    def bind_to_cog(self, cog: Any) -> None:
        """Binds the scheduled task to a cog and compiles cron expressions with dynamic seeding."""
        seed_name = f"{cog.__class__.__name__}.{self.callback.__name__}"
        self.cron_schedules = [CronExpression(expr, seed=seed_name) for expr in self.raw_schedules]

    def match(self, dt: datetime) -> bool:
        """Checks if the given datetime matches any of the registered schedules."""
        return any(cron.is_now(dt) for cron in self.cron_schedules)

    async def try_invoke(self, cog: Any, dt: datetime, on_ready: bool = False) -> None:
        """Executes the task callback if execution conditions match the target datetime."""
        if on_ready:
            if self.on_ready:
                await self.invoke(cog)
            return

        if self.match(dt):
            await self.invoke(cog)

    async def invoke(self, cog: Any) -> None:
        """Directly executes the target callback function on the cog instance."""
        await self.callback(cog)


class TaskScheduler:
    """Manages task scheduling, registration, and precise ticking loops."""

    def __init__(self, bot: Any, scheduled_tasks_timeout: int = 300) -> None:
        self.bot = bot
        self.scheduled_tasks_timeout = scheduled_tasks_timeout
        self.tasks: dict[str, list[tuple[Any, ScheduledTask]]] = {}
        self.tick_task: asyncio.Task | None = None
        self.bg_tasks: set[asyncio.Task] = set()

    def register_cog_tasks(self, cog: Any) -> None:
        """Discovers and registers all ScheduledTasks defined on the cog instance."""
        cog_name = cog.__class__.__name__
        tasks_list: list[tuple[Any, ScheduledTask]] = []

        for name in dir(cog):
            try:
                attr = getattr(cog, name, None)
            except Exception:
                continue

            if isinstance(attr, ScheduledTask):
                attr.bind_to_cog(cog)
                tasks_list.append((cog, attr))

        if tasks_list:
            self.tasks[cog_name] = tasks_list

    def unregister_cog_tasks(self, cog_name: str) -> None:
        """Removes all tasks registered under the specified cog name."""
        self.tasks.pop(cog_name, None)

    def has_sub_minute_tasks(self) -> bool:
        """Checks if any registered task has explicit sub-minute seconds precision."""
        for task_list in self.tasks.values():
            for _, task in task_list:
                for cron in task.cron_schedules:
                    if cron.has_explicit_seconds_field:
                        return True
        return False

    async def start(self) -> None:
        """Starts the scheduler execution tick loop."""
        if self.tick_task is not None:
            return
        self.tick_task = asyncio.create_task(self.run_loop())

    def stop(self) -> None:
        """Stops the scheduler execution tick loop."""
        if self.tick_task:
            self.tick_task.cancel()
            self.tick_task = None

    async def run_loop(self) -> None:
        """Execution tick loop that dynamically adjusts intervals based on seconds precision."""
        # Fire initial on_ready invoke
        await self.invoke_tasks(on_ready=True)

        while not self.bot.is_closed():
            use_seconds_precision: bool = self.has_sub_minute_tasks()

            if use_seconds_precision:
                sleep_sec: float = 1 - (time.time() % 1)
            else:
                sleep_sec = 60 - (time.time() % 60)

            await asyncio.sleep(sleep_sec)

            task = asyncio.create_task(self.invoke_tasks())
            self.bg_tasks.add(task)
            task.add_done_callback(self.bg_tasks.discard)

    async def invoke_tasks(self, on_ready: bool = False) -> None:
        """Invokes all matching scheduled tasks concurrently with timeout boundaries."""
        now = self.bot.now()
        tasks = []

        for task_list in self.tasks.values():
            for cog, task in task_list:
                tasks.append(
                    asyncio.wait_for(
                        task.try_invoke(cog, now, on_ready),
                        self.scheduled_tasks_timeout,
                    )
                )

        if not tasks:
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                import traceback

                traceback.print_exception(None, value=result, tb=result.__traceback__)
