from discord.ext import commands
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


class Time(commands.Cog):
    @dataclass
    class Config:
        timezone: str = "UTC"
        extras: dict[str, str] = field(default_factory=dict)

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    def server_now(self, ctx) -> datetime:
        tz = self.bot.guild_config(ctx.guild).get("timezone", self.config.timezone)
        zone = ZoneInfo(tz)
        return datetime.now(zone)

    def now(self):
        zone = ZoneInfo(self.config.timezone)
        return datetime.now(zone)

    def template_variables(self, ctx):
        result = {"now": self.server_now(ctx), "utcnow": datetime.now(timezone.utc)}

        for name, tz in self.config.extras.items():
            result[f"now_{name}"] = datetime.now(ZoneInfo(tz))

        return result
