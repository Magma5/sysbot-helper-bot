import email.policy
import traceback
from email import message_from_string
from email.message import EmailMessage
from io import BytesIO

from aiohttp import web
from discord import Embed, File
from discord.ext import commands
from markdownify import markdownify

from sysbot_helper.api import APIRouter, json_response
from sysbot_helper.api_utils import send_to_channel
from sysbot_helper.bot import Bot


def body_get(body, name):
    field = body.get(name, "")
    if isinstance(field, bytes):
        return field.decode("utf8")
    if isinstance(field, web.FileField):
        return field.file.read().decode("utf8")
    return field


def body_get_bytes(body, name):
    field = body.get(name, b"")
    if isinstance(field, web.FileField):
        return field.file.read()
    return field


class ApiSendgrid(commands.Cog):
    router = APIRouter(prefix="/api/sendgrid")

    def __init__(self, bot: Bot):
        self.bot = bot
        self.bot.api.add_router(self.router, self)

    @router.post("/{channel_id:[0-9]+}")
    async def send_message_sendgrid(self, request: web.Request):
        channel_id = int(request.match_info["channel_id"])

        body = await request.post()
        content = []
        content.append(f'**From**: {body_get(body, "from")}')
        content.append(f'**To**: {body_get(body, "to")}')
        content.append(f'**Subject**: {body_get(body, "subject")}')
        content.append("")

        files = []
        try:
            eml: EmailMessage = message_from_string(body_get(body, "email"), policy=email.policy.default)
            eml_body = eml.get_body()
            if eml_body:
                md = markdownify(eml_body.get_content())
                content.append(md)

            for attachment in eml.iter_attachments():
                value = attachment.get_payload(decode=True)
                if value and isinstance(value, bytes):
                    files.append(File(BytesIO(value), filename=attachment.get_filename()))

        except Exception:
            content.append("Cannot parse email body!")
            traceback.print_exc()

            eml_data = body_get_bytes(body, "email")
            if eml_data:
                files.append(File(BytesIO(eml_data), filename="message.eml"))

        embed = Embed(description="\n".join(content))

        response_data = await send_to_channel(self.bot, channel_id, embed=embed, files=files)
        return json_response(response_data)
