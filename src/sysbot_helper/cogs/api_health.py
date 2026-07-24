from aiohttp import web
from discord.ext import commands

from sysbot_helper.api import APIRouter
from sysbot_helper.bot import Bot


class ApiHealth(commands.Cog):
    """Provides basic healthcheck endpoints for the API server."""

    router = APIRouter()

    def __init__(self, bot: Bot):
        self.bot = bot

    @router.get("/hello")
    async def hello(self, _):
        return web.Response(text="hello, world!\n")

    @router.get("/healthcheck")
    async def health_check(self, _):
        return web.Response(text="OK")
