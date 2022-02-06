from dataclasses import dataclass, field
from time import time
from typing import Union
from discord.errors import HTTPException
from discord.ext import commands, tasks
from contextlib import suppress
from collections import deque, namedtuple
from random import gauss
import asyncio


@dataclass
class ChannelInfo:
    message_text: str
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
    @dataclass
    class Config:
        channels: dict[Union[int, str], str]
        check_message_history: int = 50
        channel_activity_wait: int = 30
        magic_space: str = "⠀"
        auto_refresh: bool = True
        auto_refresh_interval: int = 30

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

        self.channels: dict[int, ChannelInfo] = {}
        # iterate through all configured channel (groups) and initialize ChannelInfo
        for channel_group in config.channels:
            for channel_id in bot.channel_groups().get(channel_group):
                info = ChannelInfo(config.channels[channel_group])
                self.channels[channel_id] = info

    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        # Find old messages from the channel
        for channel_id, info in self.channels.items():
            async with info.lock:
                history = await self.get_message_history(channel_id)
                info.message_history.extend(history)
        if self.config.auto_refresh:
            self.auto_refresh.start()

    async def get_message_history(self, channel_id):
        channel = self.bot.get_channel(channel_id)
        history = []
        async for message in channel.history(limit=self.config.check_message_history):
            if message.author == self.bot.user and message.content.endswith(self.config.magic_space):
                history.append(message)
        return history

    async def refresh_message(self, channel_id):
        channel = self.bot.get_channel(channel_id)
        info = self.channels[channel_id]

        # Generate a fake context given the values we have.
        # Can't have an actual context because Message object is missing
        Context = namedtuple('Context', 'bot guild channel author')
        ctx = Context(self.bot, channel.guild, channel, self.bot.user)
        variables = self.bot.template_variables(ctx)

        # Render template
        template = self.bot.template_env.from_string(info.message_text)
        content = template.render(variables).strip() + self.config.magic_space
        queue = info.message_history

        # Use API to retrieve history, so that it handles deleted messages as well
        last_message_id = 0
        async for message in channel.history(limit=1):
            last_message_id = message.id

        async with info.lock:
            # Try to clean old messages
            while queue and queue[-1].id != last_message_id:
                with suppress(HTTPException):
                    await queue.pop().delete()

            try:
                if queue[-1].content != content:
                    await queue[-1].edit(content=content)
                    return True
                return False
            except (IndexError, HTTPException):
                # Send new message, if history is empty
                message = await channel.send(content)
                queue.append(message)
                return True

    @tasks.loop()
    async def auto_refresh(self):
        for channel_id, info in self.channels.items():
            if info.wait.locked():
                continue
            if await self.refresh_message(channel_id):
                await asyncio.sleep(gauss(5, 1))
        interval = self.config.auto_refresh_interval
        await asyncio.sleep(interval, interval / 5)

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
