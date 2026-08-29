import unittest
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import LinkPreviewOptions, ReplyParameters
from PIL import Image

from sysbot_helper.cogs.telegram import ChatLink, Telegram
from sysbot_helper.cogs.utils.discord_action import DiscordMessage


class TestTelegramSync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.mock_bot = MagicMock()
        self.mock_bot.user.id = 1
        self.mock_bot.template_engine.render_string.return_value = "Rendered Telegram Content"

        self.mock_aiogram_bot = AsyncMock()
        self.mock_aiogram_bot.edit_message_text = AsyncMock()
        self.mock_aiogram_bot.send_message = AsyncMock()
        self.mock_aiogram_bot.send_document = AsyncMock()
        self.mock_aiogram_bot.delete_message = AsyncMock()

        self.chat_link = ChatLink(bot="primary_bot", channel=100, chat=200)
        self.config = Telegram.Config(
            bots={"primary_bot": "token_mock"},
            chat_link=[self.chat_link],
        )

        with patch("aiogram.Bot") as mock_bot_cls, patch("aiogram.client.session.aiohttp.AiohttpSession"):
            mock_bot_cls.return_value = self.mock_aiogram_bot
            self.telegram_cog = Telegram(self.mock_bot, self.config)
            self.telegram_cog.bots["primary_bot"] = self.mock_aiogram_bot

    async def test_on_message_edit_passes_keyword_arguments(self) -> None:
        before_message = MagicMock()
        before_message.content = "Original text"

        after_message = MagicMock()
        after_message.content = "Updated text"
        after_message.author.id = 10
        after_message.channel.id = 100

        with patch.object(self.telegram_cog, "get_by_discord", new=AsyncMock(return_value=301)):
            await self.telegram_cog.on_message_edit(before_message, after_message)

        self.mock_aiogram_bot.edit_message_text.assert_awaited_once_with(
            chat_id=200,
            message_id=301,
            text="Rendered Telegram Content",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

    async def test_on_message_passes_keyword_arguments_and_reply_parameters(self) -> None:
        message = MagicMock()
        message.author.id = 10
        message.channel.id = 100
        message.reference = MagicMock()
        message.attachments = []

        sent_msg_mock = MagicMock()
        sent_msg_mock.message_id = 401
        self.mock_aiogram_bot.send_message.return_value = sent_msg_mock

        with (
            patch.object(self.telegram_cog, "get_by_discord", new=AsyncMock(return_value=302)),
            patch.object(self.telegram_cog, "add_message_mapping", new=AsyncMock()),
        ):
            await self.telegram_cog.on_message(message)

        self.mock_aiogram_bot.send_message.assert_awaited_once_with(
            chat_id=200,
            text="Rendered Telegram Content",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_parameters=ReplyParameters(message_id=302),
        )

    async def test_on_message_with_attachment_passes_keyword_arguments(self) -> None:
        attachment_mock = AsyncMock()
        attachment_mock.read.return_value = b"test file content"
        attachment_mock.filename = "sample.txt"

        message = MagicMock()
        message.author.id = 10
        message.channel.id = 100
        message.reference = None
        message.attachments = [attachment_mock]

        sent_msg_mock = MagicMock()
        sent_msg_mock.message_id = 401
        self.mock_aiogram_bot.send_message.return_value = sent_msg_mock

        doc_msg_mock = MagicMock()
        doc_msg_mock.message_id = 402
        self.mock_aiogram_bot.send_document.return_value = doc_msg_mock

        with (
            patch.object(self.telegram_cog, "get_by_discord", new=AsyncMock(return_value=None)),
            patch.object(self.telegram_cog, "add_message_mapping", new=AsyncMock()),
        ):
            await self.telegram_cog.on_message(message)

        self.mock_aiogram_bot.send_document.assert_awaited_once()
        _, call_kwargs = self.mock_aiogram_bot.send_document.call_args
        self.assertEqual(call_kwargs["chat_id"], 200)
        self.assertEqual(call_kwargs["document"].filename, "sample.txt")
        self.assertEqual(call_kwargs["reply_parameters"], ReplyParameters(message_id=401))

    async def test_on_message_delete_passes_keyword_arguments(self) -> None:
        message = MagicMock()
        message.author.id = 10
        message.channel.id = 100

        with patch.object(self.telegram_cog, "get_all_by_discord", new=AsyncMock(return_value=[501, 502])):
            await self.telegram_cog.on_message_delete(message)

        self.assertEqual(self.mock_aiogram_bot.delete_message.await_count, 2)
        self.mock_aiogram_bot.delete_message.assert_any_await(chat_id=200, message_id=501)
        self.mock_aiogram_bot.delete_message.assert_any_await(chat_id=200, message_id=502)

    async def test_discord_message_from_telegram_static_sticker_resampling(self) -> None:
        image_stream = BytesIO()
        sample_image = Image.new("RGB", (300, 300), color="red")
        sample_image.save(image_stream, format="PNG")
        image_stream.seek(0)

        mock_bot = AsyncMock()
        mock_bot.download.return_value = image_stream

        mock_sticker = MagicMock()
        mock_sticker.is_animated = False
        mock_sticker.file_unique_id = "test_sticker_1"

        mock_telegram_message = MagicMock()
        mock_telegram_message.sticker = mock_sticker
        mock_telegram_message.document = None
        mock_telegram_message.photo = None
        mock_telegram_message.video = None
        mock_telegram_message.video_note = None
        mock_telegram_message.voice = None

        discord_message = await DiscordMessage.from_telegram(mock_bot, mock_telegram_message)

        self.assertIn("files", discord_message.message)
        self.assertEqual(len(discord_message.message["files"]), 1)
        attached_file = discord_message.message["files"][0]
        self.assertEqual(attached_file.filename, "test_sticker_1.webp")
