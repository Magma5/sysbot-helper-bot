import re
import asyncio
from discord.ext.commands import Bot
from discord.ext import commands

from dataclasses import dataclass
from discord.message import Message

from .utils import wait_tasks_any, wait_tasks_all, DiscordAction, ensure_list


@dataclass
class ReactMatcher:
    def __init__(self, bot, embeds_check_delay=1.5):
        self._bot = bot
        self.match_groups = {}
        self.embeds_check_delay = embeds_check_delay

    def _re_match(self, pattern: re.Pattern, text: str):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern)
        result = pattern.match(text)
        if result:
            self.match_groups.update(result.groupdict())
        return result

    async def content_type(self, message: Message, pattern: str):
        """Check if any attachment matches content type regex."""
        if not message.attachments:
            return False

        for attachment in message.attachments:
            if attachment.content_type and self._re_match(pattern, attachment.content_type):
                return True
        return False

    async def media(self, message: Message):
        """Check if the message contains an image or video (attachments or embeds)"""
        content_type_pattern = re.compile(r'^(image|video)/', re.IGNORECASE)
        if await self.content_type(message, content_type_pattern):
            return True

        # It take a bit of time for user embeds to show up.
        # Wait a little before checking the embeds.
        if not await self.embeds(message):
            return False

        return any(e.image or e.video for e in message.embeds)

    async def embeds(self, message: Message):
        for _ in range(int(self.embeds_check_delay / 0.1)):
            if message.embeds:
                return True
            await asyncio.sleep(0.1)
        return False

    async def content(self, message: Message, pattern: str):
        """Check if the message content matches regex."""
        content_pattern = re.compile(pattern, re.DOTALL | re.IGNORECASE)
        return self._re_match(content_pattern, message.content) is not None

    async def attachment_name(self, message: Message, pattern: str):
        """Check if attachment file name matches regex."""
        if not message.attachments:
            return False

        pattern = re.compile(pattern, re.DOTALL | re.IGNORECASE)
        for attachment in message.attachments:
            if self._re_match(pattern, attachment.filename):
                return True
        return False

    async def bot(self, message: Message):
        return message.author.bot

    async def has_permission(self, message: Message, permission):
        perm = message.author.guild_permissions
        if permission not in perm.VALID_FLAGS:
            raise ValueError(f'{permission} is not a valid permission!')
        return getattr(perm, permission) is not False

    async def channel(self, message: Message, channel_id: int):
        return message.channel.id == channel_id

    async def channels(self, message: Message, channel_id: int):
        return await self.channel(message, channel_id)

    async def guild(self, message: Message, guild_id: int):
        return message.guild.id == guild_id

    async def guilds(self, message: Message, guild_id: int):
        return await self.guild(message, guild_id)

    async def author(self, message: Message, author_id: int):
        return message.author.id == author_id

    async def authors(self, message: Message, author_id: int):
        return await self.author(message, author_id)

    async def category(self, message: Message, category_id: int):
        return message.channel.category_id == category_id

    async def categories(self, message: Message, category_id: int):
        return await self.category(category_id)

    async def mentions(self, message: Message, user_id: int):
        return user_id in message.raw_mentions

    async def mentions_role(self, message: Message, role_id: int):
        return role_id in message.raw_role_mentions

    async def mentions_channel(self, message: Message, channel_id: int):
        return channel_id in message.raw_channel_mentions

    async def mentions_self(self, message: Message):
        return await self.mentions(message, self._bot.user.id)

    async def any(self, _):
        return True

    async def all(self, _):
        return True


@dataclass
class ReactConfig:
    def __init__(self, **kwargs):
        # General configs
        self.embeds_check_delay = kwargs.pop('embeds_check_delay', 1.5)

        # Define default rules
        self.rules = {
            'bot': False
        }

        # Populate rules dict by checking the keys
        for k in list(kwargs.keys()):
            k_ = k.lower()
            if k.endswith('!'):
                k_ = k[:-1]
            if k_ == 'match' or hasattr(ReactMatcher, k_):
                self.rules[k] = kwargs.pop(k)

        # The remaining keys are all actions
        self.actions = ensure_list(kwargs.pop('actions', dict()))
        self.actions.insert(0, dict(**kwargs))

    async def match_helper_bool(self, fn, message, expected):
        return await fn(message) is expected

    async def match_helper_inverted(self, fn, message, arg):
        return not await fn(message, arg)

    def get_match_helper_rules(self, matcher):
        async def run_match_match(message, rules):
            tasks = []
            for name, args in rules.items():
                args = ensure_list(args)
                coro = self.match_item(matcher, name, message, *args)
                tasks.append(asyncio.create_task(coro))
            return await wait_tasks_all(tasks)
        return run_match_match

    async def match_item(self, matcher, name, message, *args):
        # Check if operation is inverted
        inverted = False
        if name.endswith('!'):
            inverted = True
            name = name[:-1]

        if name == 'match':
            fn = self.get_match_helper_rules(matcher)
        else:
            fn = getattr(matcher, name)

        tasks = []
        for arg in args:
            # Set value to null to skip the check entirely
            if arg is None:
                continue

            if isinstance(arg, bool):
                coro = self.match_helper_bool(fn, message, arg != inverted)
            elif inverted:
                coro = self.match_helper_inverted(fn, message, arg)
            else:
                coro = fn(message, arg)
            tasks.append(asyncio.create_task(coro))
        return await wait_tasks_any(tasks)

    async def check_match(self, bot, message: Message):
        matcher = ReactMatcher(bot)
        if await self.match_item(matcher, 'match', message, self.rules):
            return matcher

    async def do_actions(self, ctx, matcher):
        react_action = DiscordAction(ctx, match_groups=matcher.match_groups)
        for actions in self.actions:
            coro_list = []
            for name, args in actions.items():
                for action_arg in ensure_list(args):
                    fn = getattr(react_action, name)
                    coro_list.append(fn(action_arg))

            if coro_list:
                await asyncio.gather(*coro_list)


class Autoreact(commands.Cog):
    """Reacts to message in a specified channel"""

    class Config:
        def __init__(self, *rules):
            self.react_configs = [ReactConfig(**rule) for rule in rules]

    def __init__(self, bot, config):
        self.bot: Bot = bot
        self.config = config

    async def do_auto_react(self, message, react_config: ReactConfig):
        """Run auto react for a single rule."""
        matcher = await react_config.check_match(self.bot, message)
        if matcher:
            # Get context when message matches
            ctx = await self.bot.get_context(message)
            await react_config.do_actions(ctx, matcher)

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        # Filter out message by itself
        if message.author == self.bot.user:
            return

        await asyncio.gather(*(self.do_auto_react(message, config)
                               for config in self.config.react_configs))
