import asyncio
from functools import cache

from discord.ext import commands
from pydantic.dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .models import Experience, User


async def get_user(ctx, session: AsyncSession):
    user_id = ctx.author.id
    guild_id = ctx.guild.id

    user = await session.get(Experience, (user_id, guild_id))
    if not user:
        user = Experience(user_id=user_id, guild_id=guild_id, experience=0, level=0)
        session.add(user)
    return user


class Level(commands.Cog):
    __feature__ = ["database"]

    @dataclass
    class Config:
        pass

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @cache
    def lock(self, guild_id, user_id):
        return asyncio.Lock()

    @commands.command()
    async def top(self, ctx):
        async with self.bot.Session.begin() as session:
            rows = await session.execute(
                select(Experience, User)
                .join(User, Experience.user_id == User.user_id)
                .where(Experience.guild_id == ctx.guild.id)
                .order_by(Experience.experience.desc())
            )

        await ctx.send(
            "\n".join(f"({row.User.name}): {row.Experience.experience}" for row in rows)
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if message.author.bot:
            return

        async with self.lock(
            message.guild.id, message.author.id
        ), self.bot.Session.begin() as session:
            await User.update(message, session)

            user = await get_user(message, session)
            user.experience += 1
            if user.experience // 10 > user.level:
                user.level += 1
                reward_msg = "GG {}! You are now **level {}**!".format(
                    message.author.name, user.level
                )
                await message.reply(reward_msg)
