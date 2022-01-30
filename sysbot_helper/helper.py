import logging

from discord.ext.commands import Bot

log = logging.getLogger(__name__)


class ConfigHelper:
    @classmethod
    def cog_name(cls, key):
        return ''.join(map(str.capitalize, key.split('_')))

    def __init__(self, bot, config):
        self.bot: Bot = bot
        self.config = config
        self.cog_list = set()

    def get_config(self, category, key=None):
        raw_config = self.config[category]

        # Filter all non-int keys as global config
        config = {k: v for k, v in raw_config if not isinstance(k, int)}

        # apply guild specific configs
        if key in raw_config:
            config.update(raw_config[key])

        return config

    def guild_config(self, ctx):
        if ctx.guild:
            return self.get_config('guilds', ctx.guild.id)
        return self.get_config('guilds')

    def channel_config(self, ctx):
        if ctx.channel:
            return self.get_config('channels', ctx.channel.id)
        return self.get_config('channels')

    def get_cog(self, key):
        return self.bot.get_cog(self.cog_name(key))

    def register_cog(self, cog_name):
        self.cog_list.add(cog_name)

    def template_variables_base(self, ctx):
        return {
            'name': ctx.author.name,
            'mention': ctx.author.mention,
            'ctx': ctx
        }

    def template_variables(self, ctx):
        """Search through all registered cogs and load variables"""
        variables = self.template_variables_base(ctx)
        for cog_name in self.cog_list:
            cog = self.get_cog(cog_name)
            if hasattr(cog, 'template_variables'):
                fn = getattr(cog, 'template_variables')
                variables.update(fn(ctx))
        return variables

    def make_command(self, **command_options):
        def wrap_command(func):
            name = command_options.pop('name')
            aliases = command_options.pop('aliases', [])

            log.info('Register command name=%s', name)

            # Check slash command and text command
            if name.startswith('/') or name.startswith('_'):
                command_deco = self.bot.slash_command
                name = name[1:]
            else:
                command_deco = self.bot.command

            # Register aliases too
            name_aliases = name.split(',')
            name, aliases = name_aliases[0], tuple(aliases + name_aliases[1:])

            # Register the actual command
            @command_deco(name=name, aliases=aliases, **command_options)
            async def _(ctx):
                respond_options = func(ctx)
                if not respond_options:
                    return
                if hasattr(ctx, 'respond'):
                    await ctx.respond(**respond_options)
                else:
                    await ctx.send(**respond_options)
        return wrap_command
