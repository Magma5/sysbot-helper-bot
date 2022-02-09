import asyncio
from contextlib import suppress
import re
from typing import Optional, Union
from discord.errors import HTTPException
from discord.ext.commands import Bot
from discord.ext import commands

from dataclasses import dataclass, field
from discord.message import Message


@dataclass
class ReactConfig:
    channel: Optional[Union[int, list[int]]] = None
    guild: Optional[Union[int, list[int]]] = None

    match_media: bool = False
    match_content: Optional[str] = None
    match_content_type: Optional[str] = None
    match_file_name: Optional[str] = None
    match_all: bool = False

    react_with: list[int] = field(default_factory=list)
    send_with: list[str] = field(default_factory=list)
    reply_with: list[str] = field(default_factory=list)
    delete: bool = False

    ignore_bots: bool = True
    embed_check_delay: float = 1.5

    # def __post_init__(self):
    #     if not isinstance(self.react_with, list):
    #         self.react_with = [self.react_with]
    #     if not isinstance(self.send_with, list):
    #         self.react_with = [self.react_with]

    @classmethod
    def _get_list(self, var):
        if not isinstance(var, list):
            return [var]
        return var

    @property
    def react_with_list(self):
        return self._get_list(self.react_with)

    @property
    def send_with_list(self):
        return self._get_list(self.send_with)

    @property
    def reply_with_list(self):
        return self._get_list(self.reply_with)

    @classmethod
    async def check_content_type(cls, message: Message, pattern: re.Pattern):
        """Check if any attachment matches content type regex."""
        if not message.attachments:
            return False

        for attachment in message.attachments:
            if attachment.content_type and pattern.match(attachment.content_type):
                return True
        return False

    async def check_match_media(self, message: Message):
        """Check if the message contains an image or video (attachments or embeds)"""
        if not self.match_media:
            return False

        content_type_pattern = re.compile(r'^(image|video)/.+', re.IGNORECASE)
        if await self.check_content_type(message, content_type_pattern):
            return True

        # It take a bit of time for user embeds to show up.
        # Wait a little before checking the embeds.
        await asyncio.sleep(self.embed_check_delay)
        if message.embeds:
            if any(e.image or e.video or e.thumbnail for e in message.embeds):
                return True
        return False

    async def check_match_content(self, message: Message):
        """Check if the message content matches regex."""
        if not self.match_content:
            return False
        content_pattern = re.compile(self.match_content, re.DOTALL | re.IGNORECASE)
        if content_pattern.match(message.content):
            return True
        return False

    async def check_match_content_type(self, message: Message):
        """Check if the attachment content type matches regex."""
        if not self.match_content_type:
            return False
        return self.check_content_type(message, re.compile(self.match_content_type))

    async def check_match_file_name(self, message: Message):
        """Check if attachment file name matches regex."""
        if not self.match_file_name:
            return False

        for attachment in message.attachments:
            if re.match(self.match_file_name, attachment.content_type, re.IGNORECASE):
                return True
        return False

    async def check_match_all(self, _):
        return self.match_all

    def check_match_channel(self, message: Message):
        """Check if message is sent from the correct channel."""
        if isinstance(self.channel, list):
            return message.channel.id in self.channel
        return message.channel.id == self.channel

    def check_match_guild(self, message: Message):
        """Check if message is sent from the correct guild."""
        if not self.guild:
            return False
        if isinstance(self.guild, list):
            return message.guild.id in self.guild
        return message.guild.id == self.guild

    async def check_match(self, message: Message):
        """Main checking method, check message against config."""

        # If channel doesn't match, reject directly
        if not (self.check_match_channel(message) or self.check_match_guild(message)):
            return False

        if self.ignore_bots and message.author.bot:
            return False

        for check in [self.check_match_all,
                      self.check_match_media,
                      self.check_match_content,
                      self.check_match_content_type,
                      self.check_match_file_name]:
            if await check(message):
                return True

        return False

    async def do_actions(self, ctx):
        template_env = self.bot.template_env
        variables = self.bot.template_variables(ctx)

        await asyncio.sleep(1.5)

        for emoji in self.react_with_list:
            if isinstance(emoji, int):
                emoji = ctx.bot.get_emoji(emoji)
            with suppress(HTTPException):
                await ctx.message.add_reaction(emoji)

        # Reply
        for message in self.reply_with_list:
            with suppress(HTTPException):
                await ctx.reply(template_env.from_string(message).render(variables))

        # Send
        for message in self.send_with_list:
            with suppress(HTTPException):
                await ctx.send(template_env.from_string(message).render(variables))

        # Delete
        if self.delete:
            with suppress(HTTPException):
                await ctx.message.delete()


class Autoreact(commands.Cog):
    """Reacts to message in a specified channel"""

    class Config:
        def __init__(self, *channels):
            self.channels = []
            for channel_config in channels:
                cfg = ReactConfig(**channel_config)
                self.channels.append(cfg)

    def __init__(self, bot, config):
        self.bot: Bot = bot
        self.config = config

        for channel in self.config.channels:
            channel.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author == self.bot.user:
            return

        # The get context will be called for every single message
        ctx = await self.bot.get_context(message)

        for react_config in self.config.channels:
            if await react_config.check_match(message):
                await react_config.do_actions(ctx)
