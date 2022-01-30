from discord.enums import ChannelType
from discord.ext import commands
from discord import File
from io import BytesIO

from dataclasses import dataclass


class Dm(commands.Cog):
    """Handle direct messaging and forward the message into a specified channel."""

    @dataclass
    class Config:
        channel: int

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.type != ChannelType.private:
            return
        if message.author == self.bot.user:
            return
        channel = self.bot.get_channel(self.config.channel)
        template = self.bot.template_env.get_template('dm/dm.md')
        await channel.send(template.render(message=message))

    @commands.Cog.listener("on_message")
    async def on_message_reply(self, message):
        if message.channel.id != self.config.channel:
            return
        if message.author == self.bot.user:
            return

        # Determine the user to send to
        user = None
        if message.reference:
            ref = message.reference.resolved
            if ref and ref.mentions and ref.author == self.bot.user:
                user = ref.mentions[0]
        elif len(message.mentions) == 1:
            user = message.mentions[0]

        if not user or user == self.bot.user:
            return await message.delete()

        # Attach files
        files = []
        for attachment in message.attachments:
            content = await attachment.read()
            io = BytesIO(content)
            files.append(File(io, filename=attachment.filename))

        content = message.content.replace(f'<@{user.id}>', '').replace(f'<@!{user.id}>', '')
        await user.send(content, files=files)
        await message.add_reaction('✅')
