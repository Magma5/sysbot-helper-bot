from cogs import CogSendError
from enum import Enum
from discord.ext import commands
from time import time
from typing import Dict, Iterable, List
from discord import slash_command, TextChannel
from dataclasses import dataclass
import asyncio


class ChannelAction(Enum):
    LOCK = 1,
    UNLOCK = 2


class Admin(CogSendError):

    @dataclass
    class Config:
        channels: List[int]
        messages: Dict
        vote_valid_seconds: int = 300
        vote_count_required: int = 3

        def get_channels(self, ctx):
            return [ctx.bot.get_channel(ch) for ch in self.channels]

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.votelock_list = {}

    async def do_channel_action(self, channels, action: ChannelAction):
        if not isinstance(channels, Iterable):
            channels = [channels]

        # Lock channels by setting send_messages for @everyone to False
        for channel in channels:
            overwrite = channel.overwrites_for(channel.guild.default_role)
            if action == ChannelAction.LOCK:
                overwrite.send_messages = False
            elif action == ChannelAction.UNLOCK:
                overwrite.send_messages = None
            await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)

    @slash_command()
    @commands.is_owner()
    async def change(self, ctx, name: str):
        name = name.strip()

        # Check if channel names need to change
        channels = [channel for channel in self.config.get_channels(ctx)
                    if channel.name != name]

        summary = ["Father, I will set these name for you.", ""]
        for channel in channels:
            summary.append("#{} ({}) -> {}".format(channel.name, channel.guild.name, name))
        await ctx.respond("\n".join(summary))

        # Edit the channel names and send an announcement
        announcement = self.bot.get_cog('Announcement')
        for channel in channels:
            try:
                # If we are rate limited then it will wait, but we want to send error instead
                await asyncio.wait_for(channel.edit(name=name), timeout=3)
                if announcement:
                    await announcement.do_announce(ctx, channel, "admin/change.md")
            except Exception as e:
                await ctx.send(f"⛔ Error editing channel {channel.name} in {channel.guild.name}: {str(e)}")

    @property
    def votelock_remain(self):
        return self.config.vote_count_required - len(self.votelock_list)

    def votelock_expire(self):
        self.votelock_list = {k: v for k, v in self.votelock_list.items()
                              if time() - v[0] <= self.config.vote_valid_seconds}

    def votelock_clear(self):
        self.votelock_list.clear()

    @commands.command()
    async def votelock(self, ctx):
        self.votelock_expire()

        if ctx.author.id in self.votelock_list:
            await ctx.send(f'You have already voted! Use {ctx.prefix}votecancel to cancel your vote.')
        elif self.votelock_remain > 1:
            await ctx.send(f'You have voted to lock the bot channels. {self.votelock_remain - 1} more votes is needed.')
        else:
            await ctx.send('You have voted to lock the bot channels. Channel will be locked shortly.')
            self.votelock_clear()
            await self.do_channel_action(self.config.channels, ChannelAction.LOCK)

        self.votelock_list[ctx.author.id] = time(), ctx.author.name, ctx.guild.name

    @commands.command()
    @commands.is_owner()
    async def votelist(self, ctx):
        self.votelock_expire()

        content = ["Votelock user list:"]
        for timestamp, author, guild in self.votelock_list.values():
            content.append('{} ({}): {:.0f}s ago'.format(author, guild, time() - timestamp))

        await ctx.send('\n'.join(content))

    @commands.command()
    async def votecancel(self, ctx):
        self.votelock_expire()
        if ctx.author.id in self.votelock_list:
            self.votelock_list.pop(ctx.author.id)
            await ctx.send(f'You vote has been removed. {self.votelock_remain} more votes is needed.')
        else:
            await ctx.send(f'You have not voted! Use {ctx.prefix}votelock to vote.')

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: TextChannel = None):
        chan = channel or ctx.channel

        overwrite = chan.overwrites_for(chan.guild.default_role)
        if overwrite.send_messages is False:
            return await ctx.send('The channel is already locked!')

        await self.do_channel_action(chan, ChannelAction.LOCK)
        await ctx.send(self.config.messages['lock'])

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: TextChannel = None):
        chan = channel or ctx.channel

        overwrite = chan.overwrites_for(chan.guild.default_role)
        if overwrite.send_messages in (None, True):
            return await ctx.send('The channel is already unlocked!')

        await self.do_channel_action(chan, ChannelAction.UNLOCK)
        await ctx.send(self.config.messages['unlock'])

    @slash_command()
    @commands.is_owner()
    async def lockall(self, ctx):
        summary = ["Father, I will lock these channels:", ""]

        channels = self.config.get_channels(ctx)
        for channel in channels:
            summary.append(f"#{channel.name} ({channel.guild.name})")

        await ctx.respond('\n'.join(summary))
        await self.do_channel_action(channels, ChannelAction.LOCK)

    @slash_command()
    @commands.is_owner()
    async def unlockall(self, ctx):
        summary = ["Father, I will unlock these channels:", ""]

        channels = self.config.get_channels(ctx)
        for channel in channels:
            summary.append(f"#{channel.name} ({channel.guild.name})")

        await ctx.respond('\n'.join(summary))
        await self.do_channel_action(channels, ChannelAction.UNLOCK)
