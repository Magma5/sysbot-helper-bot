import logging

from discord import Intents, Message, Interaction, ApplicationContext
from discord.ext.commands import Bot as Base, Context, Command
from jinja2 import Environment, FileSystemLoader

from .helper import ConfigHelper
from .slash import MySlashCommand

log = logging.getLogger(__name__)


class Bot(Base):
    def __init__(self, config):
        bot_args = config.pop('bot', {})

        # Set intents from config
        intents_config = bot_args.pop('intents', {})
        intents = Intents.default()
        for k, v in intents_config.items():
            setattr(intents, k, v)

        super().__init__(**bot_args, intents=intents)

        self.helper = ConfigHelper(self, config)
        self.template_env = Environment(
            loader=FileSystemLoader("templates"))
        self.features = set()

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

    def set_database(self, database_url: str):
        """Initialize database session if needed. """
        if database_url is None:
            return
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        engine = create_async_engine(database_url)
        self.Session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        self.features.add('database')

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

            # Register aliases too
            name_aliases = name.split(',') + aliases

            log.info('Register command name=%s', name_aliases)

            for name in name_aliases:
                name = name.strip()
                if len(name) <= 0:
                    continue
                elif name[:1] in '/_':
                    async def callback(ctx):
                        await ctx.respond(**func(ctx))
                    cmd = MySlashCommand(callback, name=name[1:], aliases=aliases, **command_options)
                    self.add_application_command(cmd)
                else:
                    async def callback(ctx):
                        await ctx.send(**func(ctx))
                    cmd = Command(callback, name=name, aliases=aliases, **command_options)
                    self.add_command(cmd)

        return wrap_command

    def feature_enabled(self, feature):
        return feature in self.features

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
