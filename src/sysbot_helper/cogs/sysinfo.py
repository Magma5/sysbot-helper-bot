import platform

from discord.ext import commands


class Sysinfo(commands.Cog):
    """Commands to look up system info."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def sysinfo(self, ctx):
        info = [
            f"**System**: {platform.system()} {platform.release()}",
            f"**Python**: {platform.python_version()} ({platform.python_implementation()})",
        ]
        if platform.system() == "Linux":
            try:
                os_release = platform.freedesktop_os_release()
                if "NAME" in os_release:
                    info.append(f"**Linux**: {os_release['NAME']}")
            except (OSError, AttributeError):
                pass

        await ctx.send("\n".join(info))
