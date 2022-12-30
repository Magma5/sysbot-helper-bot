from discord.ext import commands

from secrets import randbits
from more_itertools import sliced
from itertools import cycle


class Ip(commands.Cog):
    """Command that returns random private IPv6/IPv4 addresses."""

    ip4_func = (
        lambda: randbits(24) | 10 << 24,
        lambda: randbits(20) | 172 << 24 | 16 << 16,
        lambda: randbits(16) | 192 << 24 | 168 << 16,
    )
    ip6_func = (lambda: randbits(120) | 0xFD << 120,)

    @classmethod
    def to_ipv6(cls, ip_bits):
        return ":".join(sliced(hex(ip_bits)[2:], 4))

    @classmethod
    def to_ipv4(cls, ip_bits):
        return ".".join(str(0xFF & ip_bits >> i) for i in range(24, -1, -8))

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ip(self, ctx, count: int = 1):
        count = max(1, count)
        ip = cycle(self.ip6_func)
        await ctx.send(
            "\n".join(map(self.to_ipv6, sorted(next(ip)() for _ in range(count))))
        )

    @commands.command()
    async def ip4(self, ctx, count: int = 1):
        count = max(1, count)
        ip = cycle(self.ip4_func)
        await ctx.send(
            "\n".join(map(self.to_ipv4, sorted(next(ip)() for _ in range(count))))
        )
