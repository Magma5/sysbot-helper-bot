from io import BytesIO

from aiohttp import web
from discord import File
from discord.ext import commands

from sysbot_helper.api import APIRouter, json_response
from sysbot_helper.api_utils import send_to_channel
from sysbot_helper.bot import Bot


class ApiS3(commands.Cog):
    router = APIRouter(prefix="/api/send_file")

    def __init__(self, bot: Bot):
        self.bot = bot
        self.bot.api.add_router(self.router, self)

    @router.head("/{channel_id:[0-9]+}")
    async def head_bucket_s3(self, request: web.Request):
        channel_id = int(request.match_info["channel_id"])
        channel = self.bot.get_channel(channel_id)
        if not channel:
            raise web.HTTPNotFound(reason=f"Channel {channel_id} not found.")
        return web.Response(status=200)

    @router.put("/{channel_id:[0-9]+}")
    async def create_bucket_s3(self, request: web.Request):
        channel_id = int(request.match_info["channel_id"])
        channel = self.bot.get_channel(channel_id)
        if not channel:
            raise web.HTTPNotFound(reason=f"Channel {channel_id} not found.")
        return web.Response(status=200)

    @router.put("/{channel_id:[0-9]+}/{filename:.+}")
    async def upload_file_s3(self, request: web.Request):
        channel_id = int(request.match_info["channel_id"])
        s3_key = request.match_info["filename"]
        filename = s3_key.split("/")[-1]

        data = await request.read()
        file = File(BytesIO(data), filename=filename)

        response_data = await send_to_channel(self.bot, channel_id, files=[file])
        return json_response(response_data)
