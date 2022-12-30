from discord.ext import commands

from .checks import is_sudo


class Variables(commands.Cog):
    """This cog registers template variables only and does not register any commands."""

    class Config:
        def __init__(self, **kwargs):
            self.variables = kwargs

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    def template_variables(self, _):
        return self.config.variables

    @commands.command()
    @is_sudo()
    async def setvariable(self, ctx, name: str, value: str):
        if name in self.config.variables:
            if not isinstance(self.config.variables[name], str):
                await ctx.send(f"Cannot set variable: {name} is not a string!")
                return
            await ctx.send(f'Variable [{name}] set to "{value}"')
        else:
            await ctx.send(f'Created new variable [{name}], set to "{value}"')
        self.config.variables[name] = value
