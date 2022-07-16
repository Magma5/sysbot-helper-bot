from asyncio.exceptions import CancelledError
from .utils.discord_action import DiscordMessage
import logging
import aiogram
from aiogram.types import Message as TelegramMessage, BufferedInputFile
from aiogram.dispatcher.dispatcher import Dispatcher
from discord import Message
from discord.ext import commands, tasks
from aiogram.client.session.aiohttp import AiohttpSession
from pydantic import BaseModel


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

    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config

        # Setting up telegram objects
        self.session = AiohttpSession()
        self.dp = Dispatcher()

        # A list of bots to poll for updates
        self.bots = {
            name: aiogram.Bot(token, session=self.session, parse_mode='HTML')
            for name, token in config.token.items()
        }

        # Chat ID mapping from telegram -> discord (chat_link)
        self.discord_channels: dict[int, ChatLink] = {}

        # Chat ID mapping from discord -> telegram (bot object, chat_link)
        self.telegram_chats: dict[int, tuple[aiogram.Bot, ChatLink]] = {}

        # Process chat_link
        for chat_link in config.chat_link:
            self.discord_channels[chat_link.chat] = chat_link
            self.telegram_chats[chat_link.channel] = self.bots[chat_link.bot], chat_link

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Receive discord message, send to telegram."""

        if message.author == self.bot.user:
            return

        if message.channel.id not in self.telegram_chats:
            return

        bot, chat_link = self.telegram_chats[message.channel.id]

        template = chat_link.telegram_message
        msg = self.bot.template_env.from_string(template).render(message=message)

        if message.content:
            telegram_msg = await bot.send_message(chat_link.chat, disable_web_page_preview=True, text=msg)
            telegram_msg_id = telegram_msg.message_id
        else:
            telegram_msg_id = 0

        for attachment in message.attachments:
            data = await attachment.read()
            telegram_document = BufferedInputFile(data, attachment.filename)
            await bot.send_document(chat_link.chat, telegram_document, reply_to_message_id=telegram_msg_id)

    async def message_handler(self, message: TelegramMessage):
        """Receive telegram message, send to discord."""

        if message.chat.id not in self.discord_channels:
            return

        chat_link = self.discord_channels[message.chat.id]
        channel = self.bot.get_partial_messageable(chat_link.channel)

        bot = aiogram.Bot.get_current()
        discord_msg = await DiscordMessage.from_telegram(bot, message)
        template = chat_link.discord_message
        discord_msg.update(template)

        await channel.send(**discord_msg.get_send(self.bot, {
            'message': message
        }))

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_updates.is_running():
            self.dp.message.register(self.message_handler)
            self.check_updates.start()

    @tasks.loop()
    async def check_updates(self):
        try:
            await self.dp.start_polling(*self.bots.values())
        except CancelledError:
            await self.session.close()
            self.check_updates.cancel()

    async def check_updates_bot(self, bot, get_updates):
        try:
            updates = await bot(get_updates)
            for update in updates:
                get_updates.offset = update.update_id + 1
                await self.dp.feed_update(bot=bot, update=update)
        except Exception as e:
            log.error("Error checking updates!", exc_info=e)
