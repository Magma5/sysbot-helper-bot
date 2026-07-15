import unittest
from unittest.mock import MagicMock

from sysbot_helper.cogs.time import Time, TimeContext
from sysbot_helper.templates import TemplateEngine
from sysbot_helper.utils import LazyContext


class TestTimeCog(unittest.TestCase):
    def test_time_context_direct_lookups(self) -> None:
        """Verifies direct timezone resolution via standard dictionary keys."""
        time_context = TimeContext(server_timezone="Europe/Berlin")

        # Test server time
        server_datetime = time_context["now"]
        self.assertIn(server_datetime.tzinfo.key, ("Europe/Berlin", "CEST", "CET"))

        # Test UTC time
        utc_datetime = time_context["utcnow"]
        self.assertEqual(str(utc_datetime.tzinfo), "UTC")

        # Test standard IANA lookup
        tokyo_datetime = time_context["Asia/Tokyo"]
        self.assertEqual(tokyo_datetime.tzinfo.key, "Asia/Tokyo")

        # Test attribute-style underscore lookup
        new_york_datetime = time_context["America_New_York"]
        self.assertEqual(new_york_datetime.tzinfo.key, "America/New_York")

    def test_time_context_invalid_timezone_raises_key_error(self) -> None:
        """Verifies that unresolvable timezone names raise KeyError."""
        time_context = TimeContext(server_timezone="UTC")

        with self.assertRaises(KeyError):
            _ = time_context["Invalid/NonExistent_Zone"]

    def test_time_context_city_shortcuts_and_multi_slash_timezones(self) -> None:
        """Verifies resolution of city shortcuts (New_York) and multi-part timezones (America_Indiana_Indianapolis)."""
        time_context = TimeContext(server_timezone="Europe/Berlin")

        # City shortcut without region prefix
        new_york_dt = time_context["New_York"]
        self.assertEqual(new_york_dt.tzinfo.key, "America/New_York")

        tokyo_dt = time_context["tokyo"]
        self.assertEqual(tokyo_dt.tzinfo.key, "Asia/Tokyo")

        # Multi-part IANA timezone with multiple underscores
        indianapolis_dt = time_context["America_Indiana_Indianapolis"]
        self.assertEqual(indianapolis_dt.tzinfo.key, "America/Indiana/Indianapolis")

    def test_time_context_contains_operator(self) -> None:
        """Verifies that 'in' operator works on TimeContext and LazyContext."""
        time_context = TimeContext(server_timezone="Europe/Berlin")
        lazy_context = LazyContext(time_context)

        self.assertIn("now", lazy_context)
        self.assertIn("utcnow", lazy_context)
        self.assertIn("Asia_Tokyo", lazy_context)
        self.assertIn("New_York", lazy_context)
        self.assertNotIn("Invalid_NonExistent_Zone_99", lazy_context)

    def test_time_cog_template_integration(self) -> None:
        """Verifies template rendering for time.now, time.utcnow, and dynamic timezones."""
        mock_bot = MagicMock()
        mock_bot.guild_config.return_value = {"timezone": "Europe/Berlin"}

        config = Time.Config(timezone="Europe/Berlin")
        cog = Time(mock_bot, config)

        mock_context = MagicMock()
        mock_context.guild = MagicMock()

        time_context = cog.template_variables(mock_context)
        lazy_time = LazyContext(time_context)
        template_variables = {"time": lazy_time}

        template_engine = TemplateEngine()

        # Test bracket notation
        rendered_bracket = template_engine.render_string("{{ time['Asia/Tokyo'].strftime('%Z') }}", template_variables)
        self.assertEqual(rendered_bracket, "JST")

        # Test property notation with underscores
        rendered_property = template_engine.render_string(
            "{{ time.America_New_York.strftime('%Z') }}", template_variables
        )
        self.assertIn(rendered_property, ("EDT", "EST"))

        # Test city shortcut in template (e.g. time.New_York)
        rendered_shortcut = template_engine.render_string("{{ time.New_York.strftime('%Z') }}", template_variables)
        self.assertIn(rendered_shortcut, ("EDT", "EST"))

        # Test default server time
        rendered_now = template_engine.render_string("{{ time.now.strftime('%Z') }}", template_variables)
        self.assertIn(rendered_now, ("CEST", "CET"))

        # Test UTC time
        rendered_utc = template_engine.render_string("{{ time.utcnow.strftime('%Z') }}", template_variables)
        self.assertEqual(rendered_utc, "UTC")
