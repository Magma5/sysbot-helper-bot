import gc
import math
import os
import platform
from datetime import timedelta
from typing import Any

import humanize

try:
    import resource
except ImportError:
    resource = None  # type: ignore[assignment]

from discord.ext import commands


def _format_duration(seconds: float) -> str:
    return humanize.precisedelta(timedelta(seconds=int(seconds)))


def _get_process_memory_mb() -> float | None:
    if resource is None:
        return None
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system() == "Darwin":
            return round(usage / (1024 * 1024), 2)
        return round(usage / 1024, 2)
    except Exception:
        return None


class Sysinfo(commands.Cog):
    """Commands and template variables for system and bot metrics."""

    def __init__(self, bot):
        self.bot = bot

    def _get_latency(self) -> tuple[str, float]:
        latency = self.bot.latency
        if latency is not None and not math.isnan(latency) and not math.isinf(latency):
            return f"{round(latency * 1000)}ms", round(latency * 1000, 2)
        return "N/A", 0.0

    def get_metrics(self) -> dict[str, Any]:
        """Collect current system and bot performance metrics eagerly."""
        uptime_seconds = self.bot.uptime
        latency_str, latency_ms = self._get_latency()

        bot_name = self.bot.user.name if self.bot.user else ""
        bot_id = self.bot.user.id if self.bot.user else None

        return {
            "system": f"{platform.system()} {platform.release()}",
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "pid": os.getpid(),
            "memory_mb": _get_process_memory_mb(),
            "gc_count": gc.get_count(),
            "uptime": _format_duration(uptime_seconds),
            "uptime_seconds": int(uptime_seconds),
            "latency": latency_str,
            "latency_ms": latency_ms,
            "bot_name": bot_name,
            "bot_id": bot_id,
            "guilds": len(self.bot.guilds),
            "users": len(self.bot.users),
            "cogs": len(self.bot.cogs),
            "commands": len(self.bot.commands),
        }

    def template_variables(self, _ctx: Any = None) -> dict[str, Any]:
        """Expose bot and system metrics to the Jinja template engine with deferred lazy evaluation."""
        return {
            "system": f"{platform.system()} {platform.release()}",
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "pid": os.getpid(),
            "memory_mb": _get_process_memory_mb,
            "gc_count": gc.get_count,
            "uptime": lambda: _format_duration(self.bot.uptime),
            "uptime_seconds": lambda: int(self.bot.uptime),
            "latency": lambda: self._get_latency()[0],
            "latency_ms": lambda: self._get_latency()[1],
            "bot_name": lambda: self.bot.user.name if self.bot.user else "",
            "bot_id": lambda: self.bot.user.id if self.bot.user else None,
            "guilds": lambda: len(self.bot.guilds),
            "users": lambda: len(self.bot.users),
            "cogs": lambda: len(self.bot.cogs),
            "commands": lambda: len(self.bot.commands),
        }

    @commands.command()
    async def sysinfo(self, ctx):
        metrics = self.get_metrics()
        info = [
            f"**System**: {metrics['system']}",
            f"**Python**: {metrics['python_version']} ({metrics['python_implementation']})",
        ]
        if platform.system() == "Linux":
            try:
                os_release = platform.freedesktop_os_release()
                if "NAME" in os_release:
                    info.append(f"**Linux**: {os_release['NAME']}")
            except (OSError, AttributeError):
                pass

        process_line = f"**Process**: PID {metrics['pid']}"
        if metrics["memory_mb"] is not None:
            process_line += f" (Memory: {metrics['memory_mb']} MB)"

        info.extend(
            [
                process_line,
                f"**Uptime**: {metrics['uptime']}",
                f"**Latency**: {metrics['latency']}",
                (
                    f"**Guilds**: {metrics['guilds']} | **Users**: {metrics['users']} | "
                    f"**Cogs**: {metrics['cogs']} | **Commands**: {metrics['commands']}"
                ),
            ]
        )

        await ctx.send("\n".join(info))
