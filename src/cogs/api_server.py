import asyncio
from contextlib import suppress
from io import BytesIO

from aiohttp import web
from discord.errors import HTTPException
from discord.ext import commands
from pydantic import BaseModel
from sysbot_helper import Bot
from sysbot_helper.utils import embed_from_dict
from discord import File

from .utils import DiscordTextParser


class DiscordHandler():
    def __init__(self, bot):
        self.bot = bot
        self.routes = [
            web.get('/hello', self.hello),
            web.get('/healthcheck', self.health_check),
            web.post('/api/send_message/{channel_id:[0-9]+}', self.send_message),
            web.post('/api/send_message', self.send_message_form),
            web.get('/api/webhooks/{channel_id:[0-9]+}', self.get_webhook),
            web.post('/api/webhooks/{channel_id:[0-9]+}', self.send_message_webhook)
        ]

    async def hello(self, _):
        return web.Response(text='hello, world!\n')

    async def health_check(self, _):
        return web.Response(text='OK')

    async def send_message(self, request):
        data = await request.text()
        parser = DiscordTextParser(data, fail_ok=True)
        discord_send = parser.make_response()
        channel_id = int(request.match_info['channel_id'])
        return await self._send_message_common(channel_id, **discord_send)

    async def send_message_form(self, request):
        data = await request.post()
        try:
            content = data['content']
            channel_id = int(data['channel_id'])
        except (AttributeError, ValueError):
            return web.json_response({
                'error': 'Some parameters are missing or incorrect from the request.'
            }, status=400)
        return await self._send_message_common(channel_id, content=content)

    async def get_webhook(self, request):
        channel_id = int(request.match_info['channel_id'])
        channel = self.bot.get_channel(channel_id)
        if not channel:
            raise web.HTTPNotFound()

        return web.json_response({
            'type': 1,
            'id': str(channel_id),
            'channel_id': str(channel_id),
            'guild_id': str(channel.guild.id),
            'application_id': None,
            'avatar': None
        })

    async def send_message_webhook(self, request: web.Request):
        channel_id = int(request.match_info['channel_id'])
        files = []
        embeds = []
        data = {}

        wait = request.query.get('wait', None) == 'true'

        if request.content_type == 'application/json':
            data = await request.json()
        elif request.content_type == 'multipart/form-data':
            multipart = await request.multipart()
            async for part in multipart:
                if part.name == 'payload_json':
                    data.update(await part.json())
                elif part.name.startswith('file['):
                    io = BytesIO(bytes(await part.read()))
                    file = File(io, filename=part.filename)
                    files.append(file)
                else:
                    data[part.name] = (await part.read()).decode('utf8')

        content = data.get('content', '')

        with suppress(KeyError):
            for embed in data.pop('embeds'):
                embeds.append(embed_from_dict(embed))

        send_message = self._send_message_common(channel_id, content=content, embeds=embeds, files=files)
        if wait:
            return await send_message

        # Create a task and run in the background
        asyncio.create_task(send_message)
        return web.Response(status=204)

    async def _send_message_common(self, channel_id, **kwargs):
        try:
            response = await self.discord_send_message(channel_id, **kwargs)
        except (web.HTTPException, HTTPException) as e:
            return web.json_response({'error': str(e)}, status=e.status)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

        return web.json_response({'message': response})

    async def discord_send_message(self, channel_id, **kwargs):
        channel = self.bot.get_channel(channel_id)

        if not channel:
            raise web.HTTPNotFound(reason='Channel %d not found.' % channel_id)

        message = await channel.send(**kwargs)

        return {
            'id': message.id,
            'channel_id': message.channel.id,
            'content': message.content
        }


class ApiServer(commands.Cog):
    """Create an HTTP server to handle requests similar to a webhook."""

    class Config(BaseModel):
        listen: str = 'localhost'
        port: int = 8080

    def __init__(self, bot: Bot, config: Config):
        self.bot = bot
        self.config = config
        self.site_task = None

    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        if self.site_task is not None:
            return

        app = web.Application()

        app.add_routes(DiscordHandler(self.bot).routes)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, self.config.listen, self.config.port)
        self.site_task = asyncio.create_task(site.start())

    def cog_unload(self) -> None:
        self.site_task.cancel()
