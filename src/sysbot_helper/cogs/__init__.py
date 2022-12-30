from discord.ext import commands
from discord.ext.commands.errors import CheckFailure, UserInputError
from discord.errors import ApplicationCommandInvokeError


class CogSendError(commands.Cog):
    async def cog_command_error(self, ctx, error):
        if isinstance(error, CheckFailure):
            if hasattr(ctx, "respond"):
                await ctx.respond(f"Failed: {str(error)}")
            else:
                await ctx.send(f"Failed: {str(error)}")
            return
        elif isinstance(error, ApplicationCommandInvokeError):
            await ctx.send(f"⛔ {str(error.__cause__)}")
        elif isinstance(error, UserInputError):
            await ctx.send(f"⚠️ {str(error)}")
        raise error
