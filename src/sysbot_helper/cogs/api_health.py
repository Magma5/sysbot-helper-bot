from aiohttp import web
from discord.ext import commands

from sysbot_helper.api import APIRouter
from sysbot_helper.bot import Bot


class ApiHealth(commands.Cog):
    """Provides basic healthcheck endpoints for the API server."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.router = APIRouter()
        
        self.router.add_get("/hello", self.hello)
        self.router.add_get("/healthcheck", self.health_check)
        
        self.bot.api.add_router(self.router)

    async def hello(self, _):
        return web.Response(text="hello, world!\n")

    async def health_check(self, _):
        return web.Response(text="OK")
