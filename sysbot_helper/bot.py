import logging
from discord import Message, Interaction, ApplicationContext
from discord.ext.commands import Bot as Base, Context
from jinja2 import Environment, FileSystemLoader

from .helper import ConfigHelper

log = logging.getLogger(__name__)


class Bot(Base):
    def __init__(self, config):
        bot_args = config.pop('bot', {})
        super().__init__(**bot_args)

        self.helper = ConfigHelper(self, config)
        self.template_env = Environment(
            loader=FileSystemLoader("templates"))

    def guild_config(self, guild):
        return self.helper.get_config('guild', guild.id)

    def channel_config(self, channel):
        return self.helper.get_config('channel', channel.id)

    def user_config(self, user):
        return self.helper.get_config('user', user.id)

    @property
    def guild_groups(self):
        return self.helper.groups['guild']

    @property
    def channel_groups(self):
        return self.helper.groups['channel']

    @property
    def user_groups(self):
        return self.helper.groups['user']

    def template_variables(self, ctx):
        """Search through all registered cogs and load variables"""
        result = self.helper.template_variables_base(ctx)
        for cog in self.cogs.values():
            if hasattr(cog, 'template_variables'):
                fn = getattr(cog, 'template_variables')
                result.update(fn(ctx))
        return result

    def make_command(self, **command_options):
        def wrap_command(func):
            name = command_options.pop('name')
            aliases = command_options.pop('aliases', [])

            log.info('Register command name=%s', name)

            # Check slash command and text command
            if name[:1] in '/_':
                command_deco = self.slash_command
                name = name[1:]
            else:
                command_deco = self.command

            # Register aliases too
            name_aliases = name.split(',')
            name, aliases = name_aliases[0], tuple(aliases + name_aliases[1:])

            # Register the actual command
            @command_deco(name=name, aliases=aliases, **command_options)
            async def _(ctx):
                response = func(ctx)
                if response:
                    if hasattr(ctx, 'respond'):
                        await ctx.respond(**response)
                    else:
                        await ctx.send(**response)
        return wrap_command

    async def on_ready(self):
        motd = self.helper.get_motd()
        if motd:
            print(motd)

    def context_attach_attributes(self, ctx):
        ctx.template_variables = lambda: self.template_variables(ctx)
        ctx.guild_config = lambda: self.guild_config(ctx.guild)
        ctx.channel_config = lambda: self.channel_config(ctx.channel)
        ctx.author_config = lambda: self.user_config(ctx.author)
        ctx.env = self.template_env
        ctx.user_groups = self.user_groups
        ctx.channel_groups = self.channel_groups
        ctx.guild_groups = self.guild_groups

    async def get_context(self, message: Message, *, cls=Context):
        ctx = await super().get_context(message, cls=cls)
        self.context_attach_attributes(ctx)
        return ctx

    async def get_application_context(self, interaction: Interaction, cls=ApplicationContext):
        ctx = await super().get_application_context(interaction, cls=cls)
        self.context_attach_attributes(ctx)
        return ctx
