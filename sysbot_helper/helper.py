import logging

from discord.ext.commands import Bot

log = logging.getLogger(__name__)


class Groups:
    def __init__(self, config):
        self.groups = {}
        self.groups['all'] = set()
        self.add_group(config)

    def add_group(self, config):
        all_members, groups = self.flatten_groups(config)
        self.groups['all'].update(all_members)
        self.groups.update(groups)

    def flatten_groups(self, config):
        groups = {}
        all_members = set()

        if isinstance(config, int):
            all_members.add(config)

        elif isinstance(config, list):
            for v in config:
                members, subgroups = self.flatten_groups(v)
                all_members.update(members)
                groups.update(subgroups)

        elif isinstance(config, dict):
            for k, v in config.items():
                members, subgroups = self.flatten_groups(v)
                all_members.update(members)
                groups[k] = members
                groups.update(subgroups)

        return all_members, groups

    def in_group(self, member_id, name):
        if name not in self.groups:
            return False
        return member_id in self.groups[name]

    def in_group_any(self, member_id, groups):
        return any(self.in_group(member_id, group) for group in groups)

    def in_group_all(self, member_id, groups):
        return all(self.in_group(member_id, group) for group in groups)

    def get(self, name):
        if isinstance(name, int):
            return set([name])
        return self.groups.get(name, set())

    def get_all(self, *names):
        result = set()
        for name in names:
            result.update(self.get(name))
        return result

    def __repr__(self) -> str:
        return self.groups.__repr__()

    def __str__(self) -> str:
        return self.groups.__str__()


class ConfigHelper:
    @classmethod
    def cog_name(cls, key):
        return ''.join(map(str.capitalize, key.split('_')))

    config_group_mappings = {
        'sudo': ('user', 'sudo'),
        'sysbot_channels': ('channel', 'sysbots')
    }

    def __init__(self, config):
        self.bot = Bot(**config.pop('bot', {}))
        self.configs = {
            'guild': config.pop('guilds', {}),
            'channel': config.pop('channels', {}),
            'user': config.pop('users', {})
        }
        self.groups = {
            'guild': Groups(config.pop('guild_groups', {})),
            'channel': Groups(config.pop('channel_groups', {})),
            'user': Groups(config.pop('user_groups', {})),
        }

        for k, v in self.config_group_mappings.items():
            if k in config:
                group_type, group_name = v
                self.groups[group_type].add_group({group_name: config.pop(k)})

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

    def guild_config(self, guild):
        if guild:
            return self.get_config('guild', guild.id)

    def channel_config(self, channel):
        if channel:
            return self.get_config('channel', channel.id)

    def channel_groups(self):
        return self.groups['channel']

    def user_groups(self):
        return self.groups['user']

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
