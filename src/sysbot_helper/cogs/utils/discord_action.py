from io import BytesIO
from discord import File
from discord.ext.commands import Context
import asyncio
from PIL import Image


class DiscordMessage:
    def __init__(self, init=None):
        self.message = {}
        if init:
            self.update(init)

    def update(self, args):
        if isinstance(args, str):
            self.message['content'] = args
        else:
            self.message.update(args)

    def add_file(self, fp, filename):
        if 'files' not in self.message:
            self.message['files'] = []
        file = File(fp, filename=filename)
        self.message['files'].append(file)

    async def send(self, ctx, variables):
        message = self.get_send(ctx.bot, variables)

        # Specify the channel to send to
        _channel = message.pop('channel', None)
        if _channel:
            channel = ctx.bot.get_channel(_channel)
        else:
            channel = ctx.channel

        return await channel.send(**message)

    def get_send(self, bot, variables):
        env = bot.template_env
        message = dict(self.message)

        # Render templates
        content = message.get('content', None)
        if content:
            message['content'] = env.from_string(content).render(variables)

        return message

    @classmethod
    async def from_telegram(cls, bot, message):
        discord_msg = cls()

        sticker = message.sticker
        if sticker:
            sticker_file = await bot.download(sticker)
            if sticker.is_animated:
                discord_msg.add_file(sticker_file, "{}.gz".format(sticker.file_unique_id))
            else:
                img = Image.open(sticker_file)
                img.thumbnail((160, 160), Image.ANTIALIAS)
                thumb = BytesIO()
                img.save(thumb, "webp")
                thumb.seek(0)
                discord_msg.add_file(thumb, "{}.webp".format(sticker.file_unique_id))

        document = message.document
        if document:
            document_file = await bot.download(document)
            discord_msg.add_file(document_file, document.file_name)

        photo = message.photo
        if photo:
            best_photo = max(photo, key=lambda x: x.width * x.height)
            photo_file = await bot.download(best_photo)
            discord_msg.add_file(photo_file, "{}.jpg".format(best_photo.file_unique_id))

        video = message.video
        if video:
            video_file = await bot.download(video)
            discord_msg.add_file(video_file, video.file_name)

        video_note = message.video_note
        if video_note:
            video_note_file = await bot.download(video_note)
            discord_msg.add_file(video_note_file, "{}.mp4".format(video_note.file_unique_id))

        voice = message.voice
        if voice:
            voice_file = await bot.download(voice)
            discord_msg.add_file(voice_file, "{}.ogg".format(voice.file_unique_id))

        return discord_msg


class DiscordAction:
    def __init__(self, ctx: Context, **variables):
        self.ctx = ctx
        self.bot = ctx.bot
        self.env = self.bot.template_env

        self.variables = self.bot.template_variables(ctx)
        self.variables.update(variables)

        self.sent_messages = []

    async def react(self, emoji):
        if isinstance(emoji, int):
            emoji = self.bot.get_emoji(emoji)
        await self.ctx.message.add_reaction(emoji)

    async def reply(self, text):
        discord_msg = DiscordMessage(text)
        discord_msg.update({'reference': self.ctx.message})
        msg = await discord_msg.send(self.ctx, self.variables)
        self.sent_messages.append(msg)

    async def send(self, text):
        discord_msg = DiscordMessage(text)
        msg = await discord_msg.send(self.ctx, self.variables)
        self.sent_messages.append(msg)

    async def delete(self, yes=True):
        if yes:
            await self.ctx.message.delete()

    async def delete_after(self, delay):
        await asyncio.sleep(delay)
        await self.delete()

    async def delete_replies_after(self, delay):
        await asyncio.sleep(delay)
        while self.sent_messages:
            msg = self.sent_messages.pop()
            await msg.delete()

    async def delay(self, delay):
        await asyncio.sleep(delay)

    async def suppress_embeds(self, yes):
        if yes:
            await self.ctx.message.edit(suppress=True)
