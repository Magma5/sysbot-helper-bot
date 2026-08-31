import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from sysbot_helper.cogs.sysinfo import Sysinfo, _format_duration, _get_process_memory_mb


class TestCogSysinfo(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.mock_bot = MagicMock()
        self.mock_bot.latency = 0.042
        self.mock_bot.user = SimpleNamespace(name="SysbotHelper", id=123456789)
        self.mock_bot.guilds = [MagicMock(), MagicMock()]
        self.mock_bot.users = [MagicMock(), MagicMock(), MagicMock()]
        self.mock_bot.cogs = {"sysinfo": MagicMock(), "commands": MagicMock()}
        self.mock_bot.commands = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        self.mock_bot.uptime = 125.0
        self.cog = Sysinfo(self.mock_bot)

    def test_format_duration(self) -> None:
        self.assertEqual(_format_duration(0), "0 seconds")
        self.assertEqual(_format_duration(45), "45 seconds")
        self.assertEqual(_format_duration(125), "2 minutes and 5 seconds")
        self.assertEqual(_format_duration(3665), "1 hour, 1 minute and 5 seconds")
        self.assertEqual(_format_duration(90065), "1 day, 1 hour, 1 minute and 5 seconds")

    def test_get_process_memory_mb(self) -> None:
        mem = _get_process_memory_mb()
        self.assertIsInstance(mem, float)
        self.assertGreaterEqual(mem, 0.0)

    def test_get_process_memory_mb_without_resource_module(self) -> None:
        from unittest.mock import patch

        with patch("sysbot_helper.cogs.sysinfo.resource", None):
            self.assertIsNone(_get_process_memory_mb())

    def test_get_metrics_structure(self) -> None:
        metrics = self.cog.get_metrics()
        self.assertIn("system", metrics)
        self.assertIn("python_version", metrics)
        self.assertIn("pid", metrics)
        self.assertIn("memory_mb", metrics)
        self.assertIn("uptime", metrics)
        self.assertIn("latency", metrics)
        self.assertEqual(metrics["latency"], "42ms")
        self.assertEqual(metrics["latency_ms"], 42.0)
        self.assertEqual(metrics["bot_name"], "SysbotHelper")
        self.assertEqual(metrics["bot_id"], 123456789)
        self.assertEqual(metrics["guilds"], 2)
        self.assertEqual(metrics["users"], 3)
        self.assertEqual(metrics["cogs"], 2)
        self.assertEqual(metrics["commands"], 4)

    def test_template_variables_mapping(self) -> None:
        from sysbot_helper.utils import LazyContext

        raw_dict = self.cog.template_variables()
        self.assertTrue(callable(raw_dict["uptime"]))
        self.assertTrue(callable(raw_dict["memory_mb"]))
        self.assertTrue(callable(raw_dict["bot_name"]))
        self.assertFalse(callable(raw_dict["system"]))
        self.assertFalse(callable(raw_dict["pid"]))

        lazy_ctx = LazyContext(raw_dict)
        self.assertEqual(lazy_ctx["bot_name"], "SysbotHelper")
        self.assertEqual(lazy_ctx["guilds"], 2)
        self.assertIsInstance(lazy_ctx["uptime_seconds"], int)

    async def test_sysinfo_command_send(self) -> None:
        mock_ctx = MagicMock()
        mock_ctx.send = AsyncMock()

        await self.cog.sysinfo.callback(self.cog, mock_ctx)

        mock_ctx.send.assert_awaited_once()
        sent_content = mock_ctx.send.call_args[0][0]
        self.assertIn("**System**:", sent_content)
        self.assertIn("**Python**:", sent_content)
        self.assertIn("**Process**:", sent_content)
        self.assertIn("**Uptime**:", sent_content)
        self.assertIn("**Latency**:", sent_content)
        self.assertIn("**Guilds**: 2", sent_content)

    async def test_sysinfo_command_send_without_memory(self) -> None:
        from unittest.mock import patch

        mock_ctx = MagicMock()
        mock_ctx.send = AsyncMock()

        with patch("sysbot_helper.cogs.sysinfo._get_process_memory_mb", return_value=None):
            await self.cog.sysinfo.callback(self.cog, mock_ctx)

        mock_ctx.send.assert_awaited_once()
        sent_content = mock_ctx.send.call_args[0][0]
        self.assertIn("**Process**: PID", sent_content)
        self.assertNotIn("Memory:", sent_content)


@pytest.mark.asyncio
async def test_template_variables_lazy_context_integration() -> None:
    from sysbot_helper.bot import Bot

    bot = Bot(config_dict={"token": "test_token"}, load_cogs=False)
    sysinfo_cog = Sysinfo(bot)
    bot.add_cog(sysinfo_cog)

    variables = bot.template_variables(None)
    assert "python_version" in variables["sysinfo"]

    rendered = bot.template_engine.render_string(
        "Bot: {{ sysinfo.python_version }}, Uptime: {{ sysinfo.uptime }}",
        variables,
    )
    assert "Bot:" in rendered
    assert "Uptime:" in rendered
