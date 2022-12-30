from discord.ext import commands
from struct import Struct
from random import Random
from datetime import datetime, timezone
from dataclasses import dataclass


class Luck(commands.Cog):
    @classmethod
    def get_luck(
        cls,
        user_id: int,
        time: datetime,
        mu,
        sigma,
        max_luck,
        period=86400,
        salt=b"luck\x00\x00\x00\x00",
    ):
        struct = Struct("<Q")
        day = time.replace(tzinfo=timezone.utc).timestamp() // period
        seed_user = struct.pack(user_id)
        seed_day = struct.pack(int(day))
        seed = salt + seed_user + seed_day
        rand = Random(seed)
        return min(max_luck, rand.gauss(mu, sigma))

    @classmethod
    def get_rating(cls, luck, levels, stars):
        rating_nums = [int(luck >= x) for x in levels]

        stars_length = len(stars) - 1  # Must be >= 2
        rating_length = len(levels) // stars_length
        rating_sums = [
            sum(rating_nums[i * stars_length : (i + 1) * stars_length])
            for i in range(rating_length)
        ]
        rating_star = [stars[::-1][x] for x in rating_sums]
        return "".join(rating_star)

    @dataclass
    class Config:
        mu: int
        sigma: int
        max_luck: int
        rating_levels: list
        rating_stars: str = "★☆"

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    def get_luck_by_id(self, ctx, id):
        time_cog = self.bot.get_cog("Time")
        if time_cog:
            now = time_cog.server_now(ctx)
        else:
            now = datetime.now()
        return self.get_luck(
            id, now, self.config.mu, self.config.sigma, self.config.max_luck
        )

    def get_rating_by_id(self, ctx, id):
        luck = self.get_luck_by_id(ctx, id)
        return self.get_rating(
            luck, self.config.rating_levels, self.config.rating_stars
        )

    def user_luck(self, ctx):
        return self.get_luck_by_id(ctx, ctx.author.id)

    def server_luck(self, ctx):
        if ctx.guild:
            return self.get_luck_by_id(ctx, ctx.guild.id)

    def user_rating(self, ctx):
        return self.get_rating_by_id(ctx, ctx.author.id)

    def server_rating(self, ctx):
        if ctx.guild:
            return self.get_rating_by_id(ctx, ctx.guild.id)

    @property
    def max_luck(self):
        return self.config.max_luck

    def template_variables(self, ctx):
        return {
            "luck": self.user_luck(ctx),
            "luck_rating": self.user_rating(ctx),
            "server_luck": self.server_luck(ctx),
            "server_luck_rating": self.server_rating(ctx),
            "max_luck": self.config.max_luck,
        }
