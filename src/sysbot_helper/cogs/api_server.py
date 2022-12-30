import asyncio
import email.policy
import re
import traceback
from contextlib import suppress
from email import message_from_string
from email.message import EmailMessage
from io import BytesIO

from aiohttp import web
from discord import Embed, File
from discord.errors import HTTPException
from discord.ext import commands
from markdownify import markdownify
from pydantic import BaseModel
from sysbot_helper import Bot
from sysbot_helper.utils import embed_from_dict

from .utils import DiscordTextParser


def body_get(body, name):
    field = body.get(name, '')
    if type(field) is bytes:
        return field.decode('utf8')
    if type(field) is web.FileField:
        return field.file.read().decode('utf8')
    return field


def body_get_bytes(body, name):
    field = body.get(name, b'')
    if type(field) is web.FileField:
        return field.file.read()
    return field


class DiscordHandler():
    def __init__(self, bot):
        self.bot = bot
        self.routes = [
            web.get('/hello', self.hello),
            web.get('/healthcheck', self.health_check),
            web.post('/api/send_message/{channel_id:[0-9]+}', self.send_message),
            web.post('/api/send_message', self.send_message_form),
            web.get('/api/webhooks/{channel_id:[0-9]+}', self.get_webhook),
            web.post('/api/webhooks/{channel_id:[0-9]+}', self.send_message_webhook),
            web.post('/api/sendgrid/{channel_id:[0-9]+}', self.send_message_sendgrid)
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
                elif re.match(r'files?(\[[0-9]\])?$', part.name):
                    io = BytesIO(bytes(await part.read()))
                    file = File(io, filename=part.filename)
                    files.append(file)
                else:
                    data[part.name] = (await part.read(decode=True)).decode('utf8')

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

    async def send_message_sendgrid(self, request: web.Request):
        channel_id = int(request.match_info['channel_id'])

        body = await request.post()
        content = []
        content.append(f'**From**: {body_get(body, "from")}')
        content.append(f'**To**: {body_get(body, "to")}')
        content.append(f'**Subject**: {body_get(body, "subject")}')
        content.append('')

        files = []
        try:
            eml: EmailMessage = message_from_string(self.body_get(body, 'email'),
                                                    policy=email.policy.default)
            eml_body = eml.get_body()
            if eml_body:
                md = markdownify.markdownify(eml_body.get_content())
                content.append(md)

            for attachment in eml.iter_attachments():
                value = attachment.get_payload(decode=True)
                if value and type(value) is bytes:
                    files.append(File(BytesIO(value), filename=attachment.get_filename()))

        except Exception:
            content.append('Cannot parse email body!')
            traceback.print_exc()

            eml_data = body_get_bytes(body, 'email')
            if eml_data:
                files.append(BytesIO(eml_data), filename='message.eml')

        embed = Embed(description='\n'.join(content))

        return await self._send_message_common(channel_id, embed=embed, files=files)

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
