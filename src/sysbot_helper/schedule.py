from datetime import datetime
from time import time
from typing import Any
import asyncio

from .cron import CronExpression, CronItem


def scheduled(*args, **kwargs):
    """Decorator for making a scheduled task from a callback function."""

    def decorator(func):
        task = ScheduledTask(*args, callback=func, **kwargs)
        return task
    return decorator


class ScheduledTask:
    def __init__(self, *cron_expr, callback, on_ready=False, seconds=None):
        self.cron_schedules = [CronExpression(expr) for expr in cron_expr]
        self.callback = callback

        self.on_ready = on_ready
        self.seconds = None
        if seconds:
            self.seconds = CronItem.Second(seconds)

    def match(self, dt: datetime):
        return any(cron.is_now(dt) for cron in self.cron_schedules)

    async def try_invoke(self, obj: Any, dt: datetime, on_ready=False):
        """Execute the callback if the given date matches the cron schedule.

        This method should be called once every minute.
        """

        if self.seconds:
            invoke_list = []

            if on_ready and self.on_ready:
                invoke_list.append(self.invoke(obj))

            if self.match(dt):
                sec = time() % 60
                for i in range(int(sec), 60):
                    if self.seconds.match(i):
                        invoke_list.append(self.invoke_later(obj, i - sec))

            await asyncio.gather(*invoke_list)
        else:
            if (on_ready and self.on_ready) or (not on_ready and self.match(dt)):
                await self.invoke(obj)

    async def invoke(self, obj):
        await self.callback(obj)

    async def invoke_later(self, obj, sleep_sec):
        await asyncio.sleep(sleep_sec)
        await self.invoke(obj)
