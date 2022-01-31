from dataclasses import dataclass
from typing import List
from discord.errors import HTTPException
from discord.ext import commands
from contextlib import suppress
from collections import deque
import asyncio


class FloatingHelp(commands.Cog):
    @dataclass
    class Config:
        channels: List
        text: str
        check_message_history: int = 50
        magic_space: str = "⠀"

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.channel_mapping = {chan_id: deque() for chan_id in self.config.channels}
        self.lock = asyncio.Lock()
        self.wait = asyncio.Lock()

    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        # Find old messages
        for chan_id in self.config.channels:
            chan = self.bot.get_partial_messageable(chan_id)
            async for message in chan.history(limit=self.config.check_message_history):
                if message.author == self.bot.user and message.content.endswith(self.config.magic_space):
                    self.channel_mapping[chan_id].append(message.id)

    async def refresh_message(self, channel_id):
        chan = self.bot.get_channel(channel_id)

        async with self.lock:
            with suppress(HTTPException):
                for msg_id in self.channel_mapping[chan.id]:
                    await chan.get_partial_message(msg_id).delete()
                self.channel_mapping[chan.id].clear()

            content = self.config.text + self.config.magic_space
            message = await chan.send(content)
            self.channel_mapping[chan.id].append(message.id)

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        chan = message.channel

        if chan.id not in self.config.channels:
            return
        if message.author == self.bot.user and message.content.endswith(self.config.magic_space):
            return
        if self.wait.locked():
            return

        async with self.wait:
            await asyncio.sleep(10)
            await self.refresh_message(chan.id)
