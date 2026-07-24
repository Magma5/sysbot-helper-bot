import asyncio
import re
from contextlib import suppress
from io import BytesIO

from aiohttp import web
from discord import File
from discord.ext import commands

from sysbot_helper.api import APIRouter, json_response
from sysbot_helper.api_utils import send_to_channel
from sysbot_helper.bot import Bot
from sysbot_helper.utils import embed_from_dict


class ApiWebhooks(commands.Cog):
    router = APIRouter(prefix="/api/webhooks")

    def __init__(self, bot: Bot):
        self.bot = bot
        self.bot.api.add_router(self.router, self)

    @router.get("/{channel_id:[0-9]+}")
    async def get_webhook(self, request: web.Request):
        channel_id = int(request.match_info["channel_id"])
        channel = self.bot.get_channel(channel_id)
        if not channel:
            raise web.HTTPNotFound(reason=f"Channel {channel_id} not found.")

        return json_response(
            {
                "type": 1,
                "id": str(channel_id),
                "channel_id": str(channel_id),
                "guild_id": str(channel.guild.id),
                "application_id": None,
                "avatar": None,
            }
        )

    @router.post("/{channel_id:[0-9]+}")
    async def send_message_webhook(self, request: web.Request):
        channel_id = int(request.match_info["channel_id"])
        files = []
        embeds = []
        data = {}

        wait = request.query.get("wait", None) == "true"

        if request.content_type == "application/json":
            data = await request.json()
        elif request.content_type == "multipart/form-data":
            multipart = await request.multipart()
            async for part in multipart:
                if part.name == "payload_json":
                    data.update(await part.json())
                elif re.match(r"files?(\[[0-9]\])?$", part.name):
                    io = BytesIO(bytes(await part.read()))
                    file = File(io, filename=part.filename)
                    files.append(file)
                else:
                    data[part.name] = (await part.read(decode=True)).decode("utf8")

        content = data.get("content", "")

        with suppress(KeyError):
            for embed in data.pop("embeds"):
                embeds.append(embed_from_dict(embed))

        send_message_coro = send_to_channel(self.bot, channel_id, content=content, embeds=embeds, files=files)
        if wait:
            response_data = await send_message_coro
            return json_response(response_data)

        # Create a task and run in the background
        asyncio.create_task(send_message_coro)
        return web.Response(status=204)
