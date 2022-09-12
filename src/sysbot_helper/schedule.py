from datetime import datetime
from typing import Any

from .cron import CronExpression


def scheduled(*args, **kwargs):
    """Decorator for making a scheduled task from a callback function."""

    def decorator(func):
        task = ScheduledTask(*args, callback=func, **kwargs)
        return task
    return decorator


class ScheduledTask:
    def __init__(self, *cron_expr, callback):
        self.cron_schedules = [CronExpression(expr) for expr in cron_expr]
        self.callback = callback

    async def try_invoke(self, obj: Any, dt: datetime):
        """Execute the callback if the given date matches the cron schedule.

        This method should be called once every minute.
        """

        if any(cron.is_now(dt) for cron in self.cron_schedules):
            await self.invoke(obj)

    async def invoke(self, obj):
        await self.callback(obj)
