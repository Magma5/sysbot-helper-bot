from asyncio.exceptions import CancelledError
from .utils import ensure_list
from .utils.discord_action import DiscordMessage
import logging
import aiogram
from aiogram import types
from aiogram.dispatcher.dispatcher import Dispatcher
from discord import Message
from discord.ext import commands, tasks
from aiogram.client.session.aiohttp import AiohttpSession


log = logging.getLogger(__name__)


class Telegram(commands.Cog):

    DISCORD_MESSAGE_DEFAULT = '**{{ message.from_user.first_name or "" }} {{ message.from_user.last_name or "" }}**: {{message.text or message.caption or ""}}'
    TELEGRAM_MESSAGE_DEFAULT = '<b>{{ message.author.name }}</b>: {{message.clean_content | e}}'

    class Config:
        def __init__(self, *bot_configs):
            # Setting up telegram objects
            session = AiohttpSession()
            self.session = session
            self.dp = Dispatcher()

            # A list of bots to poll for updates
            self.bots = []

            # Chat ID mapping from telegram -> discord (chat_link)
            self.discord_channels = {}

            # Chat ID mapping from discord -> telegram (bot object, chat_link)
            self.telegram_chats = {}

            for config in bot_configs:
                token = config.pop('token')
                bot = aiogram.Bot(token, session=self.session, parse_mode="HTML")
                self.bots.append(bot)

                # Process chat_link
                for chat_link in ensure_list(config.get('chat_link')):
                    chat = chat_link['chat']
                    channel = chat_link['channel']
                    self.discord_channels[chat] = chat_link
                    self.telegram_chats[channel] = bot, chat_link

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Receive discord message, send to telegram."""

        if message.author == self.bot.user:
            return

        if message.channel.id not in self.config.telegram_chats:
            return

        bot, chat_link = self.config.telegram_chats[message.channel.id]

        template = chat_link.get('telegram_message', self.TELEGRAM_MESSAGE_DEFAULT)
        msg = self.bot.template_env.from_string(template).render(message=message)
        await bot.send_message(chat_link['chat'], disable_web_page_preview=True, text=msg)

    async def message_handler(self, message: types.Message):
        """Receive telegram message, send to discord."""

        if message.chat.id not in self.config.discord_channels:
            return

        chat_link = self.config.discord_channels[message.chat.id]
        channel = self.bot.get_partial_messageable(chat_link['channel'])

        bot = aiogram.Bot.get_current()
        discord_msg = await DiscordMessage.from_telegram(bot, message)
        template = chat_link.get('discord_message', self.DISCORD_MESSAGE_DEFAULT)
        discord_msg.update(template)

        await channel.send(**discord_msg.get_send(self.bot, {
            'message': message
        }))

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_updates.is_running():
            self.config.dp.message.register(self.message_handler)
            self.check_updates.start()

    @tasks.loop()
    async def check_updates(self):
        try:
            await self.config.dp.start_polling(*self.config.bots)
        except CancelledError:
            await self.config.session.close()
            self.check_updates.cancel()

    async def check_updates_bot(self, bot, get_updates):
        try:
            updates = await bot(get_updates)
            for update in updates:
                get_updates.offset = update.update_id + 1
                await self.config.dp.feed_update(bot=bot, update=update)
        except Exception as e:
            log.error("Error checking updates!", exc_info=e)
