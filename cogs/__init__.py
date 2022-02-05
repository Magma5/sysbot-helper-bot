from .parser import DiscordTextParser
from discord.ext import commands
from discord.ext.commands.errors import CheckFailure
from discord.commands.errors import ApplicationCommandInvokeError

__all__ = ['DiscordTextParser']


class CogSendError(commands.Cog):
    async def cog_command_error(self, ctx, error):
        if isinstance(error, CheckFailure):
            if hasattr(ctx, 'respond'):
                await ctx.respond(f"Failed: {str(error)}")
            else:
                await ctx.send(f"Failed: {str(error)}")
        elif isinstance(error, ApplicationCommandInvokeError):
            await ctx.send(f"⛔ {str(error.__cause__)}")
        raise error
