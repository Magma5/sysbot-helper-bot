import re
from discord.enums import ChannelType
from discord.errors import Forbidden
from discord.ext import commands
from discord import File
from io import BytesIO

from dataclasses import dataclass
from discord.message import Message


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
    async def on_message_reply(self, message: Message):
        if message.channel.id != self.config.channel:
            return
        if message.author == self.bot.user:
            return

        # Determine the user ID to send to
        user_id = None
        content = message.content

        # Reply the bot message, or mention the user or begin message with user ID
        if message.reference:
            ref = message.reference.resolved
            if ref and ref.raw_mentions and ref.author == self.bot.user:
                user_id = ref.raw_mentions[0]
        else:
            match = re.search(r'^(?:([0-9]{15,20})|<@!?([0-9]{15,20})>)\s*(.*)', content, flags=re.DOTALL)
            if match:
                user_id = int(match.group(1) or match.group(2))
                content = match.group(3)

        # Check user ID and fetch the user to send DM
        if not user_id or user_id == self.bot.user.id:
            return await message.delete()

        user = await self.bot.get_or_fetch_user(user_id)
        if not user:
            return await message.delete()

        # Attach files
        files = []
        for attachment in message.attachments:
            data = await attachment.read()
            io = BytesIO(data)
            files.append(File(io, filename=attachment.filename))

        try:
            await user.send(content, files=files)
        except Forbidden:
            await message.add_reaction('❌')
            await message.add_reaction('4️⃣')
            await message.add_reaction('0️⃣')
            await message.add_reaction('3️⃣')
        except Exception:
            await message.delete()
            raise
        else:
            await message.add_reaction('✅')
