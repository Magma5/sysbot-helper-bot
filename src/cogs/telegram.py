from contextlib import suppress
import logging
from asyncio.exceptions import CancelledError

import aiogram
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.dispatcher.dispatcher import Dispatcher
from aiogram.types import BufferedInputFile
from aiogram.types import Message as TelegramMessage
from discord import Message
from discord.ext import commands, tasks
from pydantic import BaseModel
from sysbot_helper import Bot

from .utils.discord_action import DiscordMessage

log = logging.getLogger(__name__)


class ChatLink(BaseModel):
    bot: str
    channel: int
    chat: int
    discord_message: str = '**{{ message.from_user.first_name or "" }} {{ message.from_user.last_name or "" }}**: {{message.text or message.caption or ""}}'
    telegram_message: str = '<b>{{ message.author.name }}</b>: {{message.clean_content | e}}'


class Telegram(commands.Cog):
    class Config(BaseModel):
        token: dict[str, str]
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
            for name, token in config.token.items()
        }

        # Chat ID mapping from telegram -> discord (chat_link)
        self.discord_channels: dict[int, ChatLink] = {}

        # Chat ID mapping from discord -> telegram (bot object, chat_link)
        self.telegram_chats: dict[int, tuple[aiogram.Bot, ChatLink]] = {}

        # Message ID mappings used to handle reply, edit and deletes
        self.telegram_mappings = {}
        self.discord_mappings = {}

        # Process chat_link
        for chat_link in config.chat_link:
            self.discord_channels[chat_link.chat] = chat_link
            self.telegram_chats[chat_link.channel] = self.bots[chat_link.bot], chat_link

    def add_message_mapping(self, discord_message: Message, telegram_messages: list[TelegramMessage]):
        self.discord_mappings[discord_message.id] = [message.message_id for message in telegram_messages]
        for message in telegram_messages:
            self.telegram_mappings[(message.chat.id, message.message_id)] = discord_message.id

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message):
        if after.author == self.bot.user:
            return

        if before.content == after.content:
            return

        with suppress(KeyError):
            bot, chat_link = self.telegram_chats[after.channel.id]
            text = self.bot.template_env.from_string(chat_link.telegram_message).render(message=after) or '(Empty message)'

            message_id = self.discord_mappings[after.id][0]
            await bot.edit_message_text(text, chat_id=chat_link.chat, message_id=message_id, disable_web_page_preview=True)

    @commands.Cog.listener()
    async def on_message_delete(self, message: Message):
        with suppress(KeyError):
            bot, chat_link = self.telegram_chats[message.channel.id]

            for message_id in self.discord_mappings[message.id]:
                await bot.delete_message(chat_link.chat, message_id)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[Message]):
        for message in messages:
            await self.on_message_delete(message)

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Receive discord message, send to telegram."""

        if message.author == self.bot.user:
            return

        if message.channel.id not in self.telegram_chats:
            return

        bot, chat_link = self.telegram_chats[message.channel.id]
        text = self.bot.template_env.from_string(chat_link.telegram_message).render(message=message) or '(Empty message)'

        mapping: list[TelegramMessage] = []

        try:
            ref_id = self.discord_mappings[message.reference.message_id][0]
            msg = await bot.send_message(chat_link.chat, disable_web_page_preview=True, text=text, reply_to_message_id=ref_id)
        except (KeyError, AttributeError):
            msg = await bot.send_message(chat_link.chat, disable_web_page_preview=True, text=text)

        mapping.append(msg)

        for attachment in message.attachments:
            data = await attachment.read()
            telegram_document = BufferedInputFile(data, attachment.filename)
            doc_msg = await bot.send_document(chat_link.chat, telegram_document, reply_to_message_id=mapping[0].message_id)
            mapping.append(doc_msg)

        self.add_message_mapping(message, mapping)

    async def message_handler(self, message: TelegramMessage):
        """Receive telegram message, send to discord."""

        # Filter any messages not intended for forwarding
        if message.chat.id not in self.discord_channels:
            return

        chat_link = self.discord_channels[message.chat.id]
        channel = self.bot.get_channel(chat_link.channel)

        bot = aiogram.Bot.get_current()

        # Convert Telegram message to discord message
        discord_msg = await DiscordMessage.from_telegram(bot, message)
        discord_msg.update(chat_link.discord_message)

        try:
            discord_ref = self.telegram_mappings[(message.chat.id, message.reply_to_message.message_id)]
            discord_msg.update({'reference': channel.get_partial_message(discord_ref)})
        except (KeyError, AttributeError):
            pass

        msg = discord_msg.get_send(self.bot, {
            'message': message
        })

        # Forward the message
        resp = await channel.send(**msg)

        self.add_message_mapping(resp, [message])

    async def edited_message_handler(self, message: TelegramMessage):
        """Receive telegram message, send to discord."""

        with suppress(KeyError):
            chat_link = self.discord_channels[message.chat.id]
            channel = self.bot.get_channel(chat_link.channel)

            bot = aiogram.Bot.get_current()

            # Convert Telegram message to discord message
            discord_msg = await DiscordMessage.from_telegram(bot, message)
            discord_msg.update(chat_link.discord_message)

            msg = discord_msg.get_send(self.bot, {
                'message': message
            })

            existing_message = self.telegram_mappings[(message.chat.id, message.message_id)]
            await channel.get_partial_message(existing_message).edit(**msg)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_updates.is_running():
            self.dp.message.register(self.message_handler)
            self.dp.edited_message.register(self.edited_message_handler)
            self.check_updates.start()

    @tasks.loop()
    async def check_updates(self):
        try:
            await self.dp.start_polling(*self.bots.values())
        except CancelledError:
            await self.session.close()
            self.check_updates.cancel()
