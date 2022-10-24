import logging
from asyncio.exceptions import CancelledError
from typing import Optional, Union

import aiogram
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.dispatcher.dispatcher import Dispatcher
from aiogram.types import BufferedInputFile
from aiogram.types import Message as TelegramMessage
from discord import Attachment, Message, MessageReference
from discord.ext import commands, tasks
from pydantic import BaseModel
from sqlalchemy import select
from sysbot_helper import Bot
from sysbot_helper.aiogram import unparse_entities

from .models import TelegramMapping
from .utils.discord_action import DiscordMessage

log = logging.getLogger(__name__)


class ChatLink(BaseModel):
    bot: str
    channel: int
    chat: int
    discord_message: str = '**{{ message.from_user.first_name or "" }} {{ message.from_user.last_name or "" }}**: {{ text }}'
    telegram_message: str = '<b>{{ message.author.name }}</b>: {{message.clean_content | e}}'


class Telegram(commands.Cog):
    class Config(BaseModel):
        bots: dict[str, str]
        chat_link: list[ChatLink]

    def __init__(self, bot: Bot, config: Config):
        self.bot = bot
        self.config = config

        # Setting up telegram objects
        self.session = AiohttpSession()
        self.dp = Dispatcher()

        # A list of Telegram bots (aiogram.Bot) to poll for updates
        self.bots = {
            name: aiogram.Bot(token, session=self.session, parse_mode='HTML')
            for name, token in config.bots.items()
        }

        # Chat ID mapping from discord channel / telegram chat -> chat link object
        self.telegram_chats = {link.chat: link for link in config.chat_link}
        self.discord_channels = {link.channel: link for link in config.chat_link}

    async def add_message_mapping(self, discord_message: Message, telegram_message: TelegramMessage, discord_attachment: Optional[Attachment] = None):
        """Save a message mapping to the database, given the message objects."""

        mapping = TelegramMapping(telegram_chat=telegram_message.chat.id,
                                  telegram_message=telegram_message.message_id,
                                  discord_channel=discord_message.channel.id,
                                  discord_message=discord_message.id)
        if discord_attachment:
            mapping.discord_attachment = discord_attachment.id

        async with self.bot.Session() as session:
            # Save the object to database
            session.add(mapping)
            await session.commit()

    async def get_by_discord(self, message: Union[Message, MessageReference]) -> Optional[int]:
        """Retrieve the telegram message ID (None if not found) by discord message."""

        if message is None:
            return

        if isinstance(message, MessageReference):
            id = message.message_id
        else:
            id = message.id

        stmt = select(TelegramMapping).where(TelegramMapping.discord_message == id, TelegramMapping.discord_attachment.is_(None))

        async with self.bot.Session() as sess:
            rows = await sess.execute(stmt)
            result = rows.first()

        if result:
            return result.TelegramMapping.telegram_message

    async def get_all_by_discord(self, *message: Message) -> list[int]:
        """Retrieve the telegram message IDs given a list of discord messages."""

        stmt = select(TelegramMapping).where(TelegramMapping.discord_message.in_([msg.id for msg in message]))

        async with self.bot.Session() as sess:
            rows = await sess.execute(stmt)

        return [result.TelegramMapping.telegram_message for result in rows]

    async def get_by_telegram(self, message: TelegramMessage):
        """Retrieve the discord message ID given the telegram message."""
        if message is None:
            return

        stmt = select(TelegramMapping).where(TelegramMapping.telegram_chat == message.chat.id, TelegramMapping.telegram_message == message.message_id)

        async with self.bot.Session() as sess:
            rows = await sess.execute(stmt)
            result = rows.first()

        if result:
            return result.TelegramMapping.discord_message

    def should_handle_discord(self, message: Message):
        return message.author != self.bot.user and message.channel.id in self.discord_channels

    def should_handle_telegram(self, message: TelegramMessage):
        return message.chat.id in self.telegram_chats

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_updates.is_running():
            self.dp.message.register(self.message_handler)
            self.dp.edited_message.register(self.edited_message_handler)
            self.check_updates.start()

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Receive discord message, send to telegram."""

        if not self.should_handle_discord(message):
            return

        chat_link = self.discord_channels[message.channel.id]
        text = self.bot.template_env.from_string(chat_link.telegram_message).render(message=message) or '(Empty message)'

        ref_id = await self.get_by_discord(message.reference)
        msg = await self.bots[chat_link.bot].send_message(chat_link.chat, disable_web_page_preview=True, text=text, reply_to_message_id=ref_id)

        await self.add_message_mapping(message, msg)

        # Handle discord attachments one by one
        for attachment in message.attachments:
            data = await attachment.read()
            telegram_document = BufferedInputFile(data, attachment.filename)
            doc_msg = await self.bots[chat_link.bot].send_document(chat_link.chat, telegram_document, reply_to_message_id=msg.message_id)
            await self.add_message_mapping(message, doc_msg, attachment)

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message):
        if not self.should_handle_discord(after):
            return

        # Do not handle if content did not change.
        if before.content == after.content:
            return

        chat_link = self.discord_channels[after.channel.id]
        text = self.bot.template_env.from_string(chat_link.telegram_message).render(message=after) or '(Empty message)'

        telegram_id = await self.get_by_discord(after)
        if telegram_id:
            await self.bots[chat_link.bot].edit_message_text(text, chat_link.chat, telegram_id,
                                                             disable_web_page_preview=True)

    @commands.Cog.listener()
    async def on_message_delete(self, message: Message):
        if not self.should_handle_discord(message):
            return

        chat_link = self.discord_channels[message.channel.id]
        telegram_ids = await self.get_all_by_discord(message)
        for id in telegram_ids:
            # Note: the bot may not have the permission to delete message.
            await self.bots[chat_link.bot].delete_message(chat_link.chat, id)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[Message]):
        if not self.should_handle_discord(messages[0]):
            # Assume: bulk delete will only contain messages from the same channel
            return

        chat_link = self.discord_channels[messages[0].channel.id]

        telegram_ids = await self.get_all_by_discord(*messages)
        for id in telegram_ids:
            await self.bots[chat_link.bot].delete_message(chat_link.chat, id)

    async def message_handler(self, message: TelegramMessage):
        """Receive telegram message, send to discord."""

        if not self.should_handle_telegram(message):
            return

        chat_link = self.telegram_chats[message.chat.id]
        channel = self.bot.get_channel(chat_link.channel)

        bot = aiogram.Bot.get_current()

        # Convert Telegram message to discord message
        discord_msg = await DiscordMessage.from_telegram(bot, message)
        discord_msg.update(chat_link.discord_message)

        # Check for reply
        discord_ref = await self.get_by_telegram(message.reply_to_message)
        if discord_ref:
            discord_msg.update({'reference': channel.get_partial_message(discord_ref)})

        msg = discord_msg.get_send(self.bot, {
            'message': message,
            'text': unparse_entities(message)
        })

        # Forward the message
        resp = await channel.send(**msg)

        await self.add_message_mapping(resp, message)

    async def edited_message_handler(self, message: TelegramMessage):
        """Sync telegram message edits to discord."""

        if not self.should_handle_telegram(message):
            return

        chat_link = self.telegram_chats[message.chat.id]

        channel = self.bot.get_channel(chat_link.channel)

        bot = aiogram.Bot.get_current()

        # Convert Telegram message to discord message
        discord_msg = await DiscordMessage.from_telegram(bot, message)
        discord_msg.update(chat_link.discord_message)

        msg = discord_msg.get_send(self.bot, {
            'message': message
        })

        existing_id = await self.get_by_telegram(message)
        if existing_id:
            await channel.get_partial_message(existing_id).edit(**msg)

    @tasks.loop()
    async def check_updates(self):
        try:
            await self.dp.start_polling(*self.bots.values())
        except CancelledError:
            await self.session.close()
            self.check_updates.cancel()
