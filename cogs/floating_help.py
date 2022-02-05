from dataclasses import dataclass, field
from time import time
from typing import Union
from discord.errors import HTTPException
from discord.ext import commands
from contextlib import suppress
from collections import deque
import asyncio


@dataclass
class ChannelInfo:
    message_text: str
    last_activity: float = field(default_factory=time)
    message_history: deque = field(default_factory=deque)
    wait: asyncio.Lock = field(default_factory=asyncio.Lock)

    def update(self):
        self.last_activity = time()

    def is_idle(self, activity_wait):
        return time() - self.last_activity > activity_wait


class FloatingHelp(commands.Cog):
    @dataclass
    class Config:
        channels: dict[Union[int, str], str]
        check_message_history: int = 50
        channel_activity_wait: int = 30
        magic_space: str = "⠀"

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

        self.channels: dict[int, ChannelInfo] = {}
        for channel_group in config.channels:
            for chan_id in bot.channel_groups().get(channel_group):
                self.channels[chan_id] = ChannelInfo(config.channels[channel_group])

        self.lock = asyncio.Lock()

    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        # Find old messages
        async with self.lock:
            for chan_id in self.channels:
                chan = self.bot.get_partial_messageable(chan_id)
                async for message in chan.history(limit=self.config.check_message_history):
                    if message.author == self.bot.user and message.content.endswith(self.config.magic_space):
                        self.channels[chan_id].message_history.append(message.id)

    async def refresh_message(self, channel_id):
        chan = self.bot.get_channel(channel_id)

        async with self.lock:
            with suppress(HTTPException):
                for msg_id in self.channels[channel_id].message_history:
                    await chan.get_partial_message(msg_id).delete()
                self.channels[channel_id].message_history.clear()

            content = self.channels[channel_id].message_text.strip() + self.config.magic_space
            message = await chan.send(content)
            self.channels[channel_id].message_history.append(message.id)

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        chan = message.channel

        if chan.id not in self.channels:
            return
        if message.author == self.bot.user and message.content.endswith(self.config.magic_space):
            return

        info = self.channels[chan.id]
        info.update()

        if info.wait.locked():
            return

        async with info.wait:
            while not info.is_idle(self.config.channel_activity_wait):
                await asyncio.sleep(0.79)
            await self.refresh_message(chan.id)
