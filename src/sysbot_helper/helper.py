import logging
from importlib import import_module

from .groups import Groups

log = logging.getLogger(__name__)


class ConfigHelper:
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

    def __init__(self, bot, config):
        self._check_deprecated_configs(config)

        self.bot = bot

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
        self.cog_config = config
        self.cog_list = set()

    def get_config(self, category, key=None):
        raw_config = self.configs[category]

        # Filter all non-int keys as global config
        config = {k: v for k, v in raw_config if not isinstance(k, int)}

        # apply guild specific configs
        if key in raw_config:
            config.update(raw_config[key])

        return config

    def get_cog(self, key):
        return self.bot.get_cog(self.cog_name(key))

    def get_motd(self):
        if not self.motd:
            return
        try:
            with open(self.motd, "r") as f:
                motd = f.read().strip()
                return motd
        except FileNotFoundError:
            log.info(f"{self.motd} not found, will not print MOTD.")

    def template_variables_base(self, ctx):
        result = {"ctx": ctx}

        if hasattr(ctx, "author"):
            result.update(name=ctx.author.name, mention=ctx.author.mention)

        return result

    def register_all_cogs(self):
        # Load the cogs from config file
        for pkg, configs in self.cog_config.items():
            for cog_key, args in configs.items():
                module_name = f"{pkg}.{cog_key}"
                cls_name = self.cog_name(cog_key)

                try:
                    module = self._load_cog_module(module_name)
                    cls = getattr(module, cls_name)
                except ModuleNotFoundError:
                    # Ignore module loading errors and continue to load the next cog
                    log.error(
                        "Unable to import package %s!", module_name, exc_info=True
                    )
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
                if hasattr(cls, "__feature__"):
                    feature_check = all(
                        self.bot.feature_enabled(feature) for feature in cls.__feature__
                    )
                    if not feature_check:
                        log.error(
                            "Unable to load cog: %s! Required features: %s",
                            cls_name,
                            cls.__feature__,
                        )
                        continue

                # Try Config inner class first, then module level config class
                if hasattr(cls, "Config"):
                    config_cls = cls.Config
                else:
                    config_cls_name = f"{cls_name}Config"
                    config_cls = getattr(module, config_cls_name, None)

                if config_cls is not None:
                    # Create a cog instance (with config) and add to the bot
                    log.info("Load cog with config: %s", cls_name)
                    if args is None:
                        instance = cls(self.bot, config_cls())
                    elif isinstance(args, dict):
                        instance = cls(self.bot, config_cls(**args))
                    elif isinstance(args, list):
                        instance = cls(self.bot, config_cls(*args))
                    else:
                        instance = cls(self.bot, config_cls(args))
                else:
                    log.info("Load cog: %s", cls_name)
                    instance = cls(self.bot)

                self.bot.add_cog(instance)
                self.cog_list.add(cls_name)

    def _load_cog_module(self, module_name):
        # Try loading cogs from within the package first
        try:
            module_name_internal = f".{module_name}"
            top_package = __name__.split(".")[0]
            return import_module(module_name_internal, package=top_package)
        except ModuleNotFoundError:
            pass

        return import_module(module_name)

    def _check_deprecated_configs(self, config):
        deprecated_keys = config.keys() & self.DEPRECATED_CONFIGS
        if deprecated_keys:
            raise ValueError(
                "The following configs are deprecated, please update!\n{}".format(
                    "\n".join(deprecated_keys)
                )
            )
