import base64
import random
import string
from dataclasses import dataclass, field

from discord.ext import commands
from discord.member import Member


class Typing(commands.Cog):
    @dataclass
    class Config:
        channels: list = field(default_factory=list)

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    # @commands.Cog.listener()
    # async def on_typing(self, channel, user, when):
    #     if channel.id not in self.config.channels:
    #         return
    #     await channel.send(f'{user.name} is typing!')

    def gen_token(self, user):
        rand = random.Random(user.id)
        base64_string = "=="
        while base64_string.find("==") != -1:
            sample_string = str(rand.randint(000000000000000000, 999999999999999999))
            sample_string_bytes = sample_string.encode("ascii")
            base64_bytes = base64.b64encode(sample_string_bytes)
            base64_string = base64_bytes.decode("ascii")
        else:
            token = (
                base64_string
                + "."
                + rand.choice(string.ascii_letters).upper()
                + "".join(rand.choice(string.ascii_letters + string.digits) for _ in range(5))
                + "."
                + "".join(rand.choice(string.ascii_letters + string.digits) for _ in range(27))
            )
        return token

    @commands.command()
    async def mypassword(self, ctx, user: Member):
        with open("password.txt") as f:
            passwords = list(filter(None, f.readlines()))
        if not user:
            rand = random.Random(ctx.author.id)
            await ctx.send(f"Your discord password is: {rand.choice(passwords)}")
        elif user.bot:
            token = self.gen_token(user)
            await ctx.send(f"Discord token for {user.name} is: {token}")
        else:
            rand = random.Random(user.id)
            await ctx.send(f"Discord password for {user.name} is: {rand.choice(passwords)}")
