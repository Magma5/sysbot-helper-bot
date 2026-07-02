import random
import traceback
from datetime import timedelta
from typing import Optional

from discord import Member, Message
from discord.channel import TextChannel
from discord.errors import HTTPException
from discord.ext import commands
from discord.ext.commands import Context
from discord.utils import snowflake_time


class Purge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(
        self,
        ctx: Context,
        members: commands.Greedy[Member],
        count: int = 1,
        channel: TextChannel = None,
    ):
        ref = ctx.message.reference

        if channel is None:
            channel = ctx.channel

        if ref and isinstance(ref.resolved, Message):
            time = snowflake_time(ref.resolved.id) - timedelta(milliseconds=1)
            messages = channel.history(after=time)
        else:
            messages = channel.history(limit=count)

        messages = await messages.flatten()

        if members:
            messages = [m for m in messages if m.author in members]

        deleted = len(messages)
        await channel.delete_messages(messages)
        await ctx.send(f"Deleted {deleted} message(s)")

    @commands.command(alias="purge_reaction")
    @commands.has_permissions(manage_messages=True)
    async def purge_reactions(
        self, ctx: Context, count: int = 1, channel: TextChannel = None
    ):
        ref = ctx.message.reference

        if channel is None:
            channel = ctx.channel

        if ref and isinstance(ref.resolved, Message):
            time = snowflake_time(ref.resolved.id) - timedelta(milliseconds=1)
            messages = channel.history(after=time)
        else:
            messages = channel.history(limit=count)

        async for message in messages:
            if message.reactions:
                await message.clear_reactions()

        await ctx.message.delete()

    @commands.command()
    async def spam_reactions(
        self,
        ctx: Context,
        count: int,
        sample: Optional[int] = 1,
        channel: Optional[TextChannel] = None,
    ):
        if channel is None:
            channel = ctx.channel

        messages = channel.history(before=ctx.message, limit=count)

        async for message in messages:
            k = min(20 - len(message.reactions), sample)
            if k <= 0:
                continue

            emojis = random.sample(ctx.guild.emojis, k)
            for emo in emojis:
                try:
                    await message.add_reaction(emo)
                except HTTPException:
                    traceback.print_exc()
