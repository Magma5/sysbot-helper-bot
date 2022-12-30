import re
from io import BytesIO

from discord import File, User, ChannelType, HTTPException, Message
from discord.ext import commands
from pydantic import BaseModel

from .utils import DiscordTextParser


class Dm(commands.Cog):
    """Handle direct messaging and forward the message into a specified channel."""

    class Config(BaseModel):
        channel: int
        forward_mentions: bool = True
        suppress_user_embeds: bool = True

        @property
        def channels(self):
            return [self.channel]

    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.channel.type != ChannelType.private:
            if not (
                self.config.forward_mentions and self.bot.user.mentioned_in(message)
            ):
                return
        if message.channel.id in self.config.channels:
            return
        if message.author == self.bot.user:
            return

        channel = self.bot.get_partial_messageable(self.config.channels[0])
        template = self.bot.template_env.get_template("dm/dm.md")
        await channel.send(template.render(message=message, embeds=message.embeds))

    @commands.Cog.listener("on_message")
    async def on_message_reply(self, message: Message):
        if message.channel.id not in self.config.channels:
            return
        if message.author.bot:
            return

        # Determine the user ID to send to
        user_id = None
        channel_id = None
        content = message.content

        # Reply the bot message, or mention the user or begin message with user ID
        if message.reference:
            ref = message.reference.resolved
            if ref and ref.author == self.bot.user:
                if ref.raw_channel_mentions:
                    channel_id = ref.raw_channel_mentions[0]
                elif ref.raw_mentions:
                    user_id = ref.raw_mentions[0]
        else:
            match_user = re.search(
                r"^(?:@?([0-9]{15,20})|<@!?([0-9]{15,20})>)\s*(.*)",
                content,
                flags=re.DOTALL,
            )
            match_channel = re.search(
                r"^(?:#([0-9]{15,20})|<#([0-9]{15,20})>)\s*(.*)",
                content,
                flags=re.DOTALL,
            )
            if match_user:
                user_id = int(match_user.group(1) or match_user.group(2))
                content = match_user.group(3)
            elif match_channel:
                channel_id = int(match_channel.group(1) or match_channel.group(2))
                content = match_channel.group(3)

        # Fetch the user or channel to send DM to
        target = None
        if user_id:
            target = await self.bot.get_or_fetch_user(user_id)
            respond_reaction = "✅"
        elif channel_id:
            target = self.bot.get_partial_messageable(channel_id)
            respond_reaction = "#️⃣"

        # Check if they are valid (Cannot send DM to a bot)
        if (
            not target
            or (isinstance(target, User) and target.bot)
            or target.id in self.config.channels
        ):
            return await message.delete()

        try:
            # Try to parse it for embeds
            response = DiscordTextParser.convert_to_response(content)

            # Attach files
            files = []
            for attachment in message.attachments:
                data = await attachment.read()
                io = BytesIO(data)
                files.append(File(io, filename=attachment.filename))

            await target.send(**response, files=files)
        except HTTPException as e:
            if e.status in (401, 402, 403):
                await message.add_reaction("❌")
                for i in str(e.status):
                    await message.add_reaction(i + "\u20e3")
            else:
                return await message.delete()
        except Exception:
            await message.delete()
            raise
        else:  # Success
            await message.add_reaction(respond_reaction)

        # Remove all annoying user embeds in DM channel
        if self.config.suppress_user_embeds and message.embeds:
            await message.edit(suppress=True)
