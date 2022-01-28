from discord.ext import commands
from time import time
from typing import Dict, List
from discord import slash_command, TextChannel
from dataclasses import dataclass


class Admin(commands.Cog):
    @dataclass
    class Config:
        channels: List[int]
        messages: Dict
        vote_valid_seconds: int = 300
        vote_count_required: int = 3

        def get_channels(self, ctx):
            for ch in self.channels:
                yield ctx.bot.get_channel(ch)

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.votelock_list = {}

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.respond(f"Check failure: {str(error)}")
        raise error

    async def do_lock_unlock(self, ctx, action, send_summary=True):
        # Gather channels needed
        channel_list = [channel for channel in self.config.get_channels(ctx)]
        if send_summary:
            summary = '\n'.join(
                channel.guild.name + ': ' + channel.name for channel in channel_list)
            await ctx.respond("Father, I will {} the channels: \n\n{}".format(action, summary))
        self.votelock_clear()

        # Lock channels by setting send_messages for @everyone to False
        for channel in channel_list:
            overwrite = channel.overwrites_for(channel.guild.default_role)
            overwrite.send_messages = False if action == "lock" else True
            await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)

    @slash_command()
    @commands.is_owner()
    async def change(self, ctx, name: str):
        name = name.strip()

        # Check if channel names need to change
        channel_list = [channel for channel in self.config.get_channels(ctx)
                        if channel.name != name]
        summary = '\n'.join("{}: {} -> {}".format(channel.guild.name, channel.name, name)
                            for channel in channel_list)
        await ctx.respond("Father, I will set the names for you.\n\n{}".format(summary))

        # Edit the channel names and send an announcement
        announcement = self.bot.get_cog('Announcement')
        for channel in channel_list:
            await channel.edit(name=name)
            if announcement:
                await announcement.do_announce(ctx, channel, "admin/change.md")

    @property
    def votelock_remain(self):
        return self.config.vote_count_required - len(self.votelock_list)

    def votelock_expire(self):
        self.votelock_list = {k: v for k, v in self.votelock_list.items()
                              if time() - v <= self.config.vote_valid_seconds}

    def votelock_clear(self):
        self.votelock_list.clear()

    @commands.command()
    async def votelock(self, ctx):
        self.votelock_expire()
        id = ctx.author.id
        if id in self.votelock_list:
            await ctx.send('You have already voted! Use {}votecancel to cancel your vote.\nYour vote will expire in {:.0f} seconds.'.format(
                ctx.bot.command_prefix, self.config.vote_valid_seconds - time() + self.votelock_list[id]))
            return
        self.votelock_list[id] = time()
        if len(self.votelock_list) < self.config.vote_count_required:
            await ctx.send('You have voted to lock the bot channels. {} more votes is needed.'.format(
                self.votelock_remain))
        else:
            await ctx.send('You have voted to lock the bot channels. Channel will be locked shortly.')
            await self.do_lock_unlock(ctx, 'lock', False)

    @commands.command()
    async def votecancel(self, ctx):
        self.votelock_expire()
        id = ctx.author.id
        if id in self.votelock_list:
            self.votelock_list.pop(id)
            await ctx.send('You vote has been removed. {} more votes is needed.'.format(
                self.votelock_remain))
        else:
            await ctx.send('You have not voted! Use {}votelock to vote.'.format(ctx.bot.command_prefix))

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: TextChannel = None):
        await ctx.message.delete()
        chan = channel or ctx.channel
        overwrite = chan.overwrites_for(chan.guild.default_role)
        overwrite.send_messages = False
        await chan.set_permissions(chan.guild.default_role, overwrite=overwrite)
        await ctx.send(self.config.messages['lock'])

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: TextChannel = None):
        await ctx.message.delete()
        chan = channel or ctx.channel
        overwrite = chan.overwrites_for(chan.guild.default_role)
        overwrite.send_messages = True
        await chan.set_permissions(chan.guild.default_role, overwrite=overwrite)
        await ctx.send(self.config.messages['unlock'])

    @slash_command()
    @commands.is_owner()
    async def lockall(self, ctx):
        await self.do_lock_unlock(ctx, 'lock')

    @slash_command()
    @commands.is_owner()
    async def unlockall(self, ctx):
        await self.do_lock_unlock(ctx, 'unlock')
