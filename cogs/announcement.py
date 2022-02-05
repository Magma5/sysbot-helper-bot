from discord import slash_command

from . import CogSendError
from .checks import is_sudo
from .parser import DiscordTextParser


class Announcement(CogSendError):
    def __init__(self, bot):
        self.bot = bot

    async def do_announce(self, ctx, channel, template, **kwargs):
        template = ctx.env.get_template(template)

        parser = DiscordTextParser(template.render(**kwargs))
        resp = parser.make_response(
            color=channel.guild.get_member(
                ctx.bot.user.id).color)
        await channel.send(**resp)

    @slash_command()
    @is_sudo()
    async def announce(self, ctx, message: str):
        admin = self.bot.get_cog('Admin')
        if not admin:
            return await ctx.respond('Admin cog is not loaded!')

        await ctx.respond((f"Father, I will announce for you:\n\n{message}"))
        for channel in admin.config.get_channels(ctx):
            await self.do_announce(ctx, channel, "admin/announce.md", message=message)
