from discord.ext import commands


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
