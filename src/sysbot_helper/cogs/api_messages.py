from aiohttp import web
from discord.ext import commands

from sysbot_helper.api import APIRouter, json_response
from sysbot_helper.api_utils import send_to_channel
from sysbot_helper.bot import Bot

from .utils import DiscordTextParser


class ApiMessages(commands.Cog):
    router = APIRouter()

    def __init__(self, bot: Bot):
        self.bot = bot

    @router.post("/api/send_message/{channel_id:[0-9]+}")
    async def send_message(self, request: web.Request):
        data = await request.text()
        parser = DiscordTextParser(data, fail_ok=True)
        discord_send = parser.make_response()
        channel_id = int(request.match_info["channel_id"])

        response_data = await send_to_channel(self.bot, channel_id, **discord_send)
        return json_response(response_data)

    @router.post("/api/send_message")
    async def send_message_form(self, request: web.Request):
        data = await request.post()
        try:
            content = data["content"]
            channel_id = int(data["channel_id"])
        except (AttributeError, ValueError, KeyError) as e:
            raise web.HTTPBadRequest(reason="Some parameters are missing or incorrect from the request.") from e

        response_data = await send_to_channel(self.bot, channel_id, content=content)
        return json_response(response_data)
