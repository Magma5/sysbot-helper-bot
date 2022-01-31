from discord.commands.errors import ApplicationCommandInvokeError
from discord import slash_command
from discord.ext import commands

from .parser import DiscordTextParser


class Announcement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.respond(f"Check failure: {str(error)}")
        elif isinstance(error, ApplicationCommandInvokeError):
            await ctx.send(f"⛔ {str(error.__cause__)}")
        raise error

    async def do_announce(self, ctx, channel, template, message=None):
        template = ctx.env.get_template(template)

        parser = DiscordTextParser(template.render(message=message))
        resp = parser.make_response(
            color=channel.guild.get_member(
                ctx.bot.user.id).color)
        await channel.send(**resp)

    @slash_command()
    @commands.is_owner()
    async def announce(self, ctx, message: str):
        admin = self.bot.get_cog('Admin')
        if not admin:
            await ctx.respond('Admin cog is not loaded!')
            return

        await ctx.respond((
            "Father, I will announce for you:\n```\n{}\n```".format(message)))
        for channel in admin.config.get_channels(ctx):
            await self.do_announce(ctx, channel, "admin/announce.md", message)
