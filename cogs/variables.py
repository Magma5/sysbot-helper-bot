from discord.ext import commands


class Variables(commands.Cog):
    """This cog registers template variables only and does not register any commands."""

    class Config:
        def __init__(self, **kwargs):
            self.variables = kwargs

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    def template_variables(self, ctx):
        # Use variables as-is first
        variables = self.config.variables

        # Process special variables
        if 'weekday_comments' in variables:
            now = self.bot.helper.server_now(ctx)
            comment = variables['weekday_comments'][now.weekday()]
            variables['comment'] = comment

        # Return variables + processed variables
        return variables
