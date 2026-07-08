import logging
from contextlib import suppress
from datetime import datetime
from importlib import import_module
from os import environ
from pathlib import Path
from types import SimpleNamespace

import yaml
from discord import ApplicationContext, Intents, Interaction, Message
from discord.ext import commands
from discord.ext.commands import Bot as Base
from discord.ext.commands import Context
from pydantic import BaseModel, TypeAdapter

from .groups import Groups
from .schedule import TaskScheduler
from .templates import TemplateEngine
from .utils import LazyContext

log = logging.getLogger(__name__)


class Bot(Base):
    @classmethod
    def cog_name(cls, key):
        return "".join(map(str.capitalize, key.split("_")))

    CONFIG_GROUP_MAPPINGS = {"sudo": "sudo", "sysbot_channels": "sysbots"}

    DEPRECATED_CONFIGS = {
        "guild_groups",
        "guild_groups_save",
        "channel_groups",
        "channel_groups_save",
        "user_groups",
        "user_groups_save",
    }

    def __init__(self, config_file: Path):
        # Open and read the config for this bot
        self.config_file = config_file
        log.info("Loading config file: %s", config_file)
        with config_file.open() as f:
            config = yaml.safe_load(f)

        self._check_deprecated_configs(config)
        self.configs = {
            "guild": config.pop("guilds", {}),
            "channel": config.pop("channels", {}),
            "user": config.pop("users", {}),
        }
        self.groups = Groups(config.pop("groups", {}), config.pop("groups_save", None))

        # Map some config from root to user/channel groups
        for name, map_to in self.CONFIG_GROUP_MAPPINGS.items():
            self.groups.update({map_to: config.pop(name, {})})

        self.motd = config.pop("motd", "motd.txt")

        # The remaining configs are used to load cogs
        self.cog_list = set()

        self.template_engine = TemplateEngine(template_dirs=["templates"])
        self.features = set()
        self.scheduler = TaskScheduler(self, scheduled_tasks_timeout=300)

        # Load database
        with suppress(KeyError):
            self.set_database(config.pop("database_url"))

        # Settings up the bot itself
        config_token = config.pop("token", None)
        self.token = environ.get("TOKEN") or config_token
        bot_args = config.pop("bot", {})

        # Set intents from config
        intents = Intents.all()
        intents_config = bot_args.pop("intents", {})
        if intents_config:
            intents = Intents.default()
            for k, v in intents_config.items():
                setattr(intents, k, v)

        super().__init__(**bot_args, intents=intents)

        # Register cogs based on configs
        self.register_all_cogs(config)

    def guild_config(self, guild):
        return self.get_config("guild", guild.id if guild else None)

    def channel_config(self, channel):
        return self.get_config("channel", channel.id if channel else None)

    def user_config(self, user):
        return self.get_config("user", user.id if user else None)

    def get_config(self, category, key=None):
        raw_config = self.configs[category]

        # Filter all non-int keys as global config
        config = {k: v for k, v in raw_config.items() if not isinstance(k, int)}

        # apply guild specific configs
        if key in raw_config:
            config.update(raw_config[key])

        return config

    def get_motd(self):
        if not self.motd:
            return
        try:
            with open(self.motd) as f:
                return f.read().strip()
        except FileNotFoundError:
            log.info(f"{self.motd} not found, will not print MOTD.")

    def template_variables_base(self, ctx):
        result = {"ctx": ctx}

        if hasattr(ctx, "author"):
            result.update(name=ctx.author.name, mention=ctx.author.mention)

        return result

    def register_all_cogs(self, config):
        # Load the cogs from config file
        for pkg_name, configs in config.items():
            # Check package name must be valid Python identifiers
            if not str.isidentifier(pkg_name):
                log.error("Invalid package name! %s", pkg_name)
                continue

            for cog_key, cog_config in configs.items():
                module_name = f"{pkg_name}.{cog_key}"
                cls_name = self.cog_name(cog_key)

                # Import the cog as Python module
                try:
                    module = self._load_cog_module(module_name)
                    cog_cls = getattr(module, cls_name)
                except ModuleNotFoundError:
                    # Ignore module loading errors and continue to load the next cog
                    log.error("Unable to import package %s!", module_name, exc_info=True)
                    continue
                except AttributeError:
                    log.error(
                        "Unable to load cog class %s from package %s!",
                        cls_name,
                        module_name,
                        exc_info=True,
                    )
                    continue

                # Check if feature is enabled
                if hasattr(cog_cls, "__feature__"):
                    feature_check = all(self.feature_enabled(feature) for feature in cog_cls.__feature__)
                    if not feature_check:
                        log.error(
                            "Unable to load cog: %s! Required features: %s",
                            cls_name,
                            cog_cls.__feature__,
                        )
                        continue

                # Try Config inner class first, then module level config class
                config_cls = getattr(module, f"{cls_name}Config", None)
                if hasattr(cog_cls, "Config"):
                    config_cls = cog_cls.Config

                if config_cls is None:
                    log.info("Load cog: %s", cls_name)
                    cog_instance = cog_cls(self)
                else:
                    log.info("Load cog with config: %s", cls_name)
                    if issubclass(config_cls, BaseModel):
                        config_instance = TypeAdapter(config_cls).validate_python(cog_config or {})
                        cog_instance = cog_cls(self, config_instance)

                    else:
                        if cog_config is None:
                            cog_instance = cog_cls(self, config_cls())
                        elif isinstance(cog_config, dict):
                            cog_instance = cog_cls(self, config_cls(**cog_config))
                        elif isinstance(cog_config, list):
                            cog_instance = cog_cls(self, config_cls(*cog_config))
                        else:
                            cog_instance = cog_cls(self, config_cls(cog_config))

                self.add_cog(cog_instance)
                self.cog_list.add(cls_name)

    def get_channels_in_group(self, *name):
        yield from filter(None, map(self.get_channel, self.groups.get_members(*name)))

    def now(self):
        time_cog = self.get_cog("Time")
        if time_cog:
            return time_cog.now()
        return datetime.now()

    def set_database(self, database_url: str):
        """Initialize database session if needed."""
        if database_url is None:
            return
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_async_engine(database_url)
        self.Session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        self.features.add("database")

    def template_variables(self, ctx):
        """Search through all registered cogs and load variables"""

        # Generate a fake context if a channel/messageable is passed directly instead of a full context
        if not hasattr(ctx, "author"):
            guild = getattr(ctx, "guild", None)
            ctx = SimpleNamespace(bot=self, guild=guild, channel=ctx, author=self.user)

        result = self.template_variables_base(ctx)
        for name, cog in self.cogs.items():
            if hasattr(cog, "template_variables"):
                namespace_key = name.lower()
                loaders = cog.template_variables(ctx)
                result[namespace_key] = LazyContext(loaders)
        return result

    def feature_enabled(self, feature):
        return feature in self.features

    async def on_ready(self):
        motd = self.get_motd()
        if motd:
            print(motd)
        await self.scheduler.start()

    def context_attach_attributes(self, ctx):
        ctx.template_variables = lambda: self.template_variables(ctx)
        ctx.guild_config = lambda: self.guild_config(ctx.guild)
        ctx.channel_config = lambda: self.channel_config(ctx.channel)
        ctx.author_config = lambda: self.user_config(ctx.author)
        ctx.template_engine = self.template_engine
        ctx.groups = self.groups
        return ctx

    # override
    async def get_context(self, message: Message, *, cls=Context):
        ctx = await super().get_context(message, cls=cls)
        return self.context_attach_attributes(ctx)

    async def get_application_context(self, interaction: Interaction, cls=ApplicationContext):
        ctx = await super().get_application_context(interaction, cls=cls)
        return self.context_attach_attributes(ctx)

    async def start(self):
        await super().start(self.token)

    def add_cog(self, cog: commands.Cog) -> None:
        super().add_cog(cog)
        self.scheduler.register_cog_tasks(cog)

    def remove_cog(self, name: str) -> commands.Cog | None:
        cog = super().remove_cog(name)
        if cog:
            self.scheduler.unregister_cog_tasks(name)
        return cog

    def _load_cog_module(self, module_name):
        # Try loading cogs from within this package first
        try:
            module_name_internal = f".{module_name}"
            top_package = __name__.split(".")[0]
            return import_module(module_name_internal, package=top_package)
        except ModuleNotFoundError:
            return import_module(module_name)

    def _check_deprecated_configs(self, config):
        deprecated_keys = config.keys() & self.DEPRECATED_CONFIGS
        if deprecated_keys:
            raise ValueError("The following configs are deprecated, please update!\n" + "\n".join(deprecated_keys))
