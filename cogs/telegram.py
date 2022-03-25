from asyncio.exceptions import CancelledError
import logging
from aiogram import types
from aiogram.dispatcher.dispatcher import Dispatcher
from aiogram.methods.get_updates import GetUpdates
from discord import Message
import discord
from discord.ext import commands, tasks
import aiogram
import asyncio
from aiogram.client.session.aiohttp import AiohttpSession


log = logging.getLogger(__name__)


class Telegram(commands.Cog):

    class Config:
        def __init__(self, *bot_configs):
            # Setting up telegram objects
            session = AiohttpSession()
            self.session = session
            self.dp = Dispatcher()

            # A list of bots to poll for updates
            self.bots = []

            # Chat mapping from telegram -> discord
            self.discord_channels = {}

            # Chat mapping from discord -> telegram
            self.telegram_chats = {}

            for config in bot_configs:
                token = config.pop('token')
                bot = aiogram.Bot(token, session=self.session, parse_mode="HTML")
                self.bots.append((bot, GetUpdates()))

                # Process chat_link
                chat_link = config['chat_link']
                chat = chat_link['chat']
                channel = chat_link['channel']
                self.discord_channels[chat] = channel
                self.telegram_chats[channel] = bot, chat

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author == self.bot.user:
            return

        if message.channel.id in self.config.telegram_chats:
            bot, chat = self.config.telegram_chats[message.channel.id]
            msg = '<b><a href="{jump_url}">#{channel_name}</a> {author}</b>\n{message}'
            await bot.send_message(chat, disable_web_page_preview=True, text=msg.format(
                jump_url=message.jump_url,
                channel_name=message.channel.name,
                author=message.author.name,
                message=message.clean_content))

    async def message_handler(self, message: types.Message):
        msg = {}
        if message.chat.id in self.config.discord_channels:
            bot = aiogram.Bot.get_current()
            channel_id = self.config.discord_channels[message.chat.id]
            channel = self.bot.get_partial_messageable(channel_id)
            if message.text:
                msg['content'] = message.text
            if message.sticker:
                sticker_file = await bot.download(message.sticker)
                file = discord.File(sticker_file, "{}.webp".format(message.sticker.file_unique_id))
                msg['file'] = file
            await channel.send(**msg)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_updates.is_running():
            self.config.dp.message.register(self.message_handler)
            self.check_updates.start()

    async def check_updates_bot(self, bot, get_updates):
        try:
            updates = await bot(get_updates)
            for update in updates:
                get_updates.offset = update.update_id + 1
                await self.config.dp.feed_update(bot=bot, update=update)
        except Exception as e:
            log.error("Error checking updates!", exc_info=e)

    @tasks.loop()
    async def check_updates(self):
        try:
            await asyncio.gather(*(self.check_updates_bot(*i) for i in self.config.bots))
            await asyncio.sleep(3)
        except CancelledError:
            await self.config.session.close()
            self.check_updates.cancel()
