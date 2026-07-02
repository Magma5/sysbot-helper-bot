import asyncio

from discord.ext import commands


class Matrix:
    @commands.command()
    async def matrix(self, ctx, text: str):
        msg = await ctx.send(self.get_matrix(text))
        repeat = 0
        while repeat < 10:
            repeat += len(text)
        for i in range(1, repeat + 1):
            await asyncio.sleep(1.5)
            await msg.edit(content=self.get_matrix(text, i))

    def get_matrix(self, text, offset=0):
        text2 = text * 2
        content = []
        for i in range(len(text)):
            ii = (i + offset) % len(text)
            content.append(" ".join(text2[len(text) - ii : len(text2) - ii]))
        return "\n".join(content)
