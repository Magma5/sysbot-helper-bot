import asyncio

from discord.ext import commands
from discord.errors import HTTPException
from pydantic import BaseModel
from .utils import DiscordTextParser

from sysbot_helper import Bot
from aiohttp import web


class ApiServer(commands.Cog):
    """Create an HTTP server to handle requests similar to a webhook."""

    class Config(BaseModel):
        listen: str = 'localhost'
        port: int = 8080

    def __init__(self, bot: Bot, config: Config):
        self.bot = bot
        self.config = config

    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        if not hasattr(self, 'site_task'):
            app = web.Application()

            app.add_routes([
                web.get('/hello', self.hello),
                web.get('/healthcheck', self.health_check),
                web.post('/api/send_message/{channel_id:[0-9]+}', self.send_message),
                web.post('/api/send_message', self.send_message_form)
            ])
            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(runner, self.config.listen, self.config.port)
            self.site_task = asyncio.create_task(site.start())

    def cog_unload(self) -> None:
        self.site_task.cancel()

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

    async def hello(self, request):
        return web.Response(text='Hello, world!\n')

    async def health_check(self, request):
        return web.Response(text='OK')

    async def _send_message_common(self, channel_id, **kwargs):
        try:
            response = await self.discord_send_message(channel_id, **kwargs)
        except (web.HTTPException, HTTPException) as e:
            return web.json_response({'error': str(e)}, status=e.status)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

        return web.json_response({'message': response})

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
