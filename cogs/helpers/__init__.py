from zoneinfo import ZoneInfo
from datetime import datetime
import logging


class ConfigHelper:
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.guilds = self.config['guilds']

    def guilds_config(self, ctx):
        # Filter all non-int keys as global config
        config = {k: v for k, v in self.guilds.items() if type(k) is not int}
        if ctx.guild.id in self.guilds:
            config.update(self.guilds[ctx.guild.id])
        return config

    @property
    def cogs_config(self):
        return self.config['cogs']

    def server_now(self, ctx) -> datetime:
        tz = self.guilds_config(ctx).get('timezone', 'UTC')
        zone = ZoneInfo(tz)
        return datetime.now(zone)

    def template_variables(self, ctx):
        """Search through all registered cogs and load variables"""
        variables = {
            'name': ctx.author.name,
            'mention': ctx.author.mention,
            'now': self.server_now(ctx)
        }
        for cog_name in self.cogs_config.keys():
            cls_name = cog_name.capitalize()
            cog = self.bot.get_cog(cls_name)
            if hasattr(cog, 'template_variables'):
                variables.update(getattr(cog, 'template_variables')(ctx))
        return variables

    def make_command(self, **command_options):
        def wrap_command(func):
            name = command_options['name']
            logging.info('Register command name=%s', name)
            if name.startswith('/') or name.startswith('$'):
                command = self.bot.slash_command
                name = name[1:]
            else:
                command = self.bot.command

            # Register aliases too
            name_aliases = name.split(',', 1)
            if len(name_aliases) > 1:
                name, aliases = name_aliases
                command_options['aliases'] = tuple(aliases)
            command_options['name'] = name

            @command(**command_options)
            async def new_command(ctx):
                respond_options = func(ctx)
                if not respond_options:
                    return
                if hasattr(ctx, 'respond'):
                    await ctx.respond(**respond_options)
                else:
                    await ctx.send(**respond_options)
        return wrap_command
