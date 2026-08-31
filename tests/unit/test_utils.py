import unittest
from unittest.mock import AsyncMock, MagicMock

from sysbot_helper.cogs.sysinfo import Sysinfo
from sysbot_helper.cogs.variables import Variables
from sysbot_helper.utils.embeds import embed_from_dict
from sysbot_helper.utils.functions import apply_obj_data
from sysbot_helper.utils.ip import to_ipv4, to_ipv6


class TestUtilsAndCogs(unittest.IsolatedAsyncioTestCase):
    def test_embed_from_dict(self) -> None:
        """Verifies converting dictionary data (including ISO8601 timestamps) to Discord Embed objects."""
        from datetime import UTC, datetime

        data = {
            "title": "Test Title",
            "description": "Test Description",
            "timestamp": "2026-08-08T00:00:00Z",
            "none_val": None,
        }
        embed = embed_from_dict(data)
        self.assertEqual(embed.title, "Test Title")
        self.assertEqual(embed.description, "Test Description")
        self.assertEqual(embed.timestamp, datetime(2026, 8, 8, 0, 0, 0, tzinfo=UTC))

    def test_apply_obj_data(self) -> None:
        """Verifies applying method calls to objects dynamically."""
        mock_obj = MagicMock()
        data = {
            "public_method": {"param": "value"},
            "_private_method": {"param": "value"},
            "non_existent": {"param": "value"},
        }
        apply_obj_data(mock_obj, data)
        mock_obj.public_method.assert_called_once_with(param="value")
        self.assertFalse(hasattr(mock_obj, "_private_method") and mock_obj._private_method.called)

    def test_ip_helpers(self) -> None:
        """Verifies IPv4 and IPv6 bitwise conversion helpers."""
        # 127.0.0.1 -> 0x7f000001 = 2130706433
        self.assertEqual(to_ipv4(2130706433), "127.0.0.1")
        self.assertEqual(to_ipv6(0x20010DB8000000000000000000000001), "2001:0db8:0000:0000:0000:0000:0000:0001")

    def test_variables_cog(self) -> None:
        """Verifies template variables retrieval in Variables cog."""
        config = Variables.Config(test_var="hello")
        cog = Variables(bot=MagicMock(), config=config)
        self.assertEqual(cog.template_variables(None), {"test_var": "hello"})

    async def test_setvariable_command(self) -> None:
        """Verifies setvariable command updates variables."""
        config = Variables.Config(my_var="old_value")
        cog = Variables(bot=MagicMock(), config=config)
        ctx = AsyncMock()

        await cog.setvariable.callback(cog, ctx, "my_var", "new_value")
        self.assertEqual(config.variables["my_var"], "new_value")
        ctx.send.assert_called_once_with('Variable [my_var] set to "new_value"')

    async def test_sysinfo_cog(self) -> None:
        """Verifies sysinfo command execution."""
        cog = Sysinfo(bot=MagicMock())
        ctx = AsyncMock()
        await cog.sysinfo.callback(cog, ctx)
        ctx.send.assert_called_once()
