from discord import slash_command
from discord.channel import TextChannel
from discord.commands.errors import ApplicationCommandInvokeError
from discord.ext import commands
from discord.member import Member


class Send(commands.Cog):
    """Send specified messages directly to channel or DM."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.respond(f"Check failure: {str(error)}")
        elif isinstance(error, ApplicationCommandInvokeError):
            await ctx.send(f"⛔ {str(error.__cause__)}")
        raise error

    @slash_command()
    @commands.is_owner()
    async def send(self, ctx, channel: TextChannel, message: str):
        await channel.send(message)
        await ctx.respond("🆗")

    @slash_command()
    @commands.is_owner()
    async def senddm(self, ctx, user: Member, message: str):
        await user.send(message)
        await ctx.respond("🆗")
