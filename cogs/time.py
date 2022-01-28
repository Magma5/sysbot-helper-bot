from discord.ext import commands
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


class Time(commands.Cog):
    @dataclass
    class Config:
        timezone: str = "UTC"

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    def server_now(self, ctx) -> datetime:
        tz = ctx.guild_config().get('timezone', self.config.timezone)
        zone = ZoneInfo(tz)
        return datetime.now(zone)

    def template_variables(self, ctx):
        return {
            'now': self.server_now(ctx)
        }
