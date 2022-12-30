from discord.ext import commands
from itertools import chain


class Hex(commands.Cog):
    """Command that converts hex values."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hex(self, ctx, *nums: str):
        values = []
        errors = []
        if len(nums) <= 0:
            return await ctx.send("Please provide a hex number!")

        for num in nums:
            try:
                values.append(int(num, 16))
            except ValueError:
                errors.append(num)

        await ctx.send('\n'.join(chain(
            ("0x%x = %d" % (value, value) for value in values),
            (f'Invalid hex number "{num}"' for num in errors)
        )))
