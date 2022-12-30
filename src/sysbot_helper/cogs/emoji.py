from discord.ext import commands
import re


class Emoji(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def emoji(self, ctx):
        content = []
        for emo in re.findall('<:[a-zA-Z0-9_]+:[0-9]+>', ctx.message.content):
            content.append(f"{emo} `{emo}`")
        if content:
            await ctx.send('\n'.join(content))
