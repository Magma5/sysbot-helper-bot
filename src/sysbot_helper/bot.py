import asyncio
import logging
import time
import traceback
from datetime import datetime
from types import SimpleNamespace

from discord import ApplicationContext, Intents, Interaction, Message, TextChannel
from discord.ext import tasks
from discord.ext.commands import Bot as Base
from discord.ext.commands import Context
from jinja2 import Environment, FileSystemLoader

from .helper import ConfigHelper
from .schedule import ScheduledTask

log = logging.getLogger(__name__)


class Bot(Base):
    def __init__(self, config):
        bot_args = config.pop('bot', {})

        # Set intents from config
        intents = Intents.all()
        intents_config = bot_args.pop('intents', {})
        if intents_config:
            intents = Intents.default()
            for k, v in intents_config.items():
                setattr(intents, k, v)

        super().__init__(**bot_args, intents=intents)

        self.helper = ConfigHelper(self, config)
        self.template_env = Environment(
            loader=FileSystemLoader("templates"))
        self.features = set()
        self.scheduled_tasks_timeout = 300
        self.bg_tasks = set()

    def guild_config(self, guild):
        return self.helper.get_config('guild', guild.id)

    def channel_config(self, channel):
        return self.helper.get_config('channel', channel.id)

    def user_config(self, user):
        return self.helper.get_config('user', user.id)

    @property
    def groups(self):
        return self.helper.groups

    def get_channels_in_group(self, *name):
        yield from filter(None,
                          map(self.get_channel, self.groups.get_members(*name)))

    def now(self):
        time_cog = self.get_cog('Time')
        if time_cog:
            return time_cog.now()
        return datetime.now()

    def set_database(self, database_url: str):
        """Initialize database session if needed. """
        if database_url is None:
            return
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_async_engine(database_url)
        self.Session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        self.features.add('database')

    def template_variables(self, ctx):
        """Search through all registered cogs and load variables"""

        # Generate a fake context without the message object
        if isinstance(ctx, TextChannel):
            ctx = SimpleNamespace(
                bot=self,
                guild=ctx.guild,
                channel=ctx,
                author=self.user)

        result = self.helper.template_variables_base(ctx)
        for cog in self.cogs.values():
            if hasattr(cog, 'template_variables'):
                fn = getattr(cog, 'template_variables')
                result.update(fn(ctx))
        return result

    def feature_enabled(self, feature):
        return feature in self.features

    async def on_ready(self):
        motd = self.helper.get_motd()
        if motd:
            print(motd)
        if not self.loop_scheduled_tasks.is_running():
            self.loop_scheduled_tasks.start()
            task = asyncio.create_task(self.invoke_scheduled_tasks(True))
            task.add_done_callback(self.bg_tasks.discard)

    @tasks.loop()
    async def loop_scheduled_tasks(self):
        sleep_sec = 60 - time.time() % 60
        await asyncio.sleep(sleep_sec)
        task = asyncio.create_task(self.invoke_scheduled_tasks()) \
            .add_done_callback(self.bg_tasks.discard)
        self.bg_tasks.add(task)

    async def invoke_scheduled_tasks(self, on_ready=False):
        now = self.now()

        tasks = []
        for cog in self.cogs.values():
            for method in cog.__class__.__dict__.values():
                if type(method) is not ScheduledTask:
                    continue
                tasks.append(asyncio.wait_for(
                    method.try_invoke(cog, now, on_ready), self.scheduled_tasks_timeout))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                traceback.print_exception(None, value=result, tb=result.__traceback__)

    def context_attach_attributes(self, ctx):
        ctx.template_variables = lambda: self.template_variables(ctx)
        ctx.guild_config = lambda: self.guild_config(ctx.guild)
        ctx.channel_config = lambda: self.channel_config(ctx.channel)
        ctx.author_config = lambda: self.user_config(ctx.author)
        ctx.env = self.template_env
        ctx.groups = self.groups

    # override
    async def get_context(self, message: Message, *, cls=Context):
        ctx = await super().get_context(message, cls=cls)
        self.context_attach_attributes(ctx)
        return ctx

    async def get_application_context(self, interaction: Interaction, cls=ApplicationContext):
        ctx = await super().get_application_context(interaction, cls=cls)
        self.context_attach_attributes(ctx)
        return ctx
