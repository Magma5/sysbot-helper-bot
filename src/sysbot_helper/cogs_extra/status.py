from dataclasses import dataclass

from discord import Activity, ActivityType, Bot, Game, Status
from discord.ext import commands


class Status(commands.Cog):
    @dataclass
    class Config:
        pass

    def __init__(self, bot, config):
        self.bot: Bot = bot
        self.config = config

    @commands.command()
    async def setplay(self, ctx, text: str):
        activity = Game(name=text)
        await self.bot.change_presence(activity=activity)

    @commands.command()
    async def setstatus(self, ctx, status: Status):
        await self.bot.change_presence(status=status)

    @commands.command()
    async def setdoing(self, ctx, type, text, status: Status = Status("idle")):
        activities = {
            "playing": ActivityType.playing,
            "streaming": ActivityType.streaming,
            "listening": ActivityType.listening,
            "watching": ActivityType.watching,
            "competing": ActivityType.competing,
        }
        activity = Activity(
            type=activities.get(type, ActivityType.playing), name=text, status=status
        )
        await self.bot.change_presence(activity=activity)
