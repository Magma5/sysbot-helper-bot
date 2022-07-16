import logging
from importlib import import_module

from .groups import Groups

log = logging.getLogger(__name__)


class ConfigHelper:
    @classmethod
    def cog_name(cls, key):
        return ''.join(map(str.capitalize, key.split('_')))

    CONFIG_GROUP_MAPPINGS = [
        ('user', 'sudo', 'sudo'),
        ('channel', 'sysbot_channels', 'sysbots')
    ]

    def __init__(self, bot, config):
        self.bot = bot
        self.configs = {
            'guild': config.pop('guilds', {}),
            'channel': config.pop('channels', {}),
            'user': config.pop('users', {})
        }
        self.groups = {
            'guild': Groups(config.pop('guild_groups', {}),
                            config.pop('guild_groups_save', None)),
            'channel': Groups(config.pop('channel_groups', {}),
                              config.pop('channel_groups_save', None)),
            'user': Groups(config.pop('user_groups', {}),
                           config.pop('user_groups_save', {})),
        }

        # Map some config from root to user/channel groups
        for group_type, name, map_to in self.CONFIG_GROUP_MAPPINGS:
            self.groups[group_type].update({map_to: config.pop(name, {})})

        self.motd = config.pop('motd', 'motd.txt')

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
            with open(self.motd, 'r') as f:
                motd = f.read().strip()
                return motd
        except FileNotFoundError:
            log.info(f'{self.motd} not found, will not print MOTD.')

    def template_variables_base(self, ctx):
        result = {'ctx': ctx}

        if hasattr(ctx, 'author'):
            result.update(
                name=ctx.author.name,
                mention=ctx.author.mention)

        return result

    def register_all_cogs(self):
        # Load the cogs from config file
        for pkg, configs in self.cog_config.items():
            for cog_key, args in configs.items():
                module_name = f"{pkg}.{cog_key}"
                cls_name = self.cog_name(cog_key)

                module = import_module(module_name)
                if not hasattr(module, cls_name):
                    log.warn('Unable to load cog %s from package %s!', cls_name, module_name)
                    continue
                cls = getattr(module, cls_name)

                # Check if feature is enabled
                if hasattr(cls, '__feature__'):
                    feature_check = all(self.bot.feature_enabled(feature) for feature in cls.__feature__)
                    if not feature_check:
                        log.warn('Unable to load cog: %s! Required features: %s', cls_name, cls.__feature__)
                        continue

                # Create a cog instance (with config) and add to the bot
                if hasattr(cls, 'Config'):
                    log.info('Load cog with config: %s', cls_name)
                    if isinstance(args, dict):
                        instance = cls(self.bot, cls.Config(**args))
                    elif isinstance(args, list):
                        instance = cls(self.bot, cls.Config(*args))
                    else:
                        instance = cls(self.bot, cls.Config(args))
                else:
                    log.info('Load cog: %s', cls_name)
                    instance = cls(self.bot)

                self.bot.add_cog(instance)
                self.cog_list.add(cls_name)
