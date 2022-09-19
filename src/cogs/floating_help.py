import asyncio
from collections import defaultdict, deque
from contextlib import suppress
from dataclasses import dataclass, field
from time import time
from typing import Union

from discord.errors import HTTPException
from discord.ext import commands
from pydantic import BaseModel
from sysbot_helper import Bot, scheduled


@dataclass
class ChannelInfo:
    message_text: str = None
    last_activity: float = field(default_factory=time)
    message_history: deque = field(default_factory=deque)

    # Wait for channel inactive to refresh a message
    wait: asyncio.Lock = field(default_factory=asyncio.Lock)

    # Lock the deque object for each channel
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def update_active(self):
        self.last_activity = time()

    def is_idle(self, activity_wait):
        return time() - self.last_activity > activity_wait


class FloatingHelp(commands.Cog):
    class Config(BaseModel):
        channels: dict[Union[int, str], str]
        check_message_history: int = 50
        channel_activity_wait: int = 30
        magic_space: str = "⠀"
        auto_refresh: bool = True
        auto_refresh_interval: int = 30
        skip_locked_channels: bool = False

    def __init__(self, bot: Bot, config: Config):
        self.bot = bot
        self.config = config

        self.channels: dict[int, ChannelInfo] = defaultdict(ChannelInfo)
        self.inactive_channels: set[int] = set()

    @property
    def resolved_channels(self):
        return list(self.bot.channels_in_group(*self.config.channels.keys()))

    async def get_message_history(self, channel_id):
        channel = self.bot.get_channel(channel_id)

        # history() returns message from newest to oldest
        async for message in channel.history(limit=self.config.check_message_history):
            if message.author == self.bot.user and message.content.endswith(self.config.magic_space):
                yield message

    async def refresh_message(self, channel_id):
        channel = self.bot.get_channel(channel_id)
        info = self.channels[channel_id]

        # Render template
        variables = self.bot.template_variables(channel)
        template = self.bot.template_env.from_string(info.message_text)
        content = template.render(variables).strip() + self.config.magic_space

        # Use API to retrieve history, so that it handles deleted messages as well
        last_message_id = 0
        async for message in channel.history(limit=1):
            last_message_id = message.id

        async with info.lock:
            # Check if channel needs skip
            if self.should_skip(channel):
                # Delete every single old messages
                for msg in info.message_history:
                    with suppress(HTTPException):
                        await msg.delete()
                return info.message_history.clear()

            # Refresh message history if not present
            if not info.message_history:
                async for msg in self.get_message_history(channel.id):
                    info.message_history.append(msg)

            # Try to clean old messages except the last message
            while info.message_history and info.message_history[-1].id != last_message_id:
                with suppress(HTTPException):
                    await info.message_history.pop().delete()

            # Edit the last message if possible, otherwise send a new one.
            try:
                if info.message_history[-1].content != content:
                    await info.message_history[-1].edit(content=content)
                    return True
                return False
            except (IndexError, HTTPException):
                # Send new message, if history is empty
                message = await channel.send(content)
                info.message_history.append(message)
                return True

    def should_skip(self, channel):
        if channel.id in self.inactive_channels:
            return True
        perms = channel.permissions_for(channel.guild.default_role)
        return self.config.skip_locked_channels and perms.send_messages is False

    @scheduled('* * * * *', seconds='*/10')
    async def auto_refresh(self):
        await self._auto_refresh()

    async def _auto_refresh(self):
        # Refresh all the channels
        channel_ids = set()
        for name, message_text in self.config.channels.items():
            for channel in self.bot.get_channels_in_group(name):
                self.channels[channel.id].message_text = message_text
                channel_ids.add(channel.id)

        # Find out which channels are no longer part of the list
        self.inactive_channels = self.channels.keys() - channel_ids

        for channel_id, info in self.channels.items():
            if info.wait.locked():
                continue

            await self.refresh_message(channel_id)

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        channel = message.channel

        if channel.id not in self.channels:
            return

        if message.author == self.bot.user and message.content.endswith(self.config.magic_space):
            return

        info = self.channels[channel.id]
        info.update_active()

        if info.wait.locked():
            return

        async with info.wait:
            while not info.is_idle(self.config.channel_activity_wait):
                await asyncio.sleep(0.29)
            await self.refresh_message(channel.id)
