import time

from discord import Activity, ActivityType, Bot, Status
from discord.ext import commands


class TestPresence(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.command()
    async def test_presence(self, ctx):
        activity = Activity(
            type=ActivityType.playing,
            name="Python",
            state="uv sync",
            timestamps={"start": int(time.time() * 1000)},
            details="Test 123",
            assets={"large_text": "DFH Stadium", "small_text": "Silver III"},
            buttons=[{"label": "Test", "url": "https://discord.com/invite/jXG77kSJmK"}],
        )
        print(activity)
        await self.bot.change_presence(activity=activity, status=Status.idle)
