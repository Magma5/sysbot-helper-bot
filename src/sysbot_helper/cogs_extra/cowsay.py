import cowsay
from discord.commands import ApplicationCommandInvokeError
from discord.commands.core import slash_command
from discord.commands.options import Option
from discord.ext import commands


class Cowsay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.respond(f"Check failure: {str(error)}")
        elif isinstance(error, ApplicationCommandInvokeError):
            await ctx.respond(f"⛔ {str(error.__cause__)}")
        raise error

    @slash_command()
    async def cowsay(
        self,
        ctx,
        text: str,
        type: Option(str, "Change cowsay graphs", choices=cowsay.char_names) = "cow",
    ):
        s = cowsay.get_output_string(type, text)
        await ctx.respond(f"```\n{s.strip()}\n```")
