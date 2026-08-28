import unittest
from datetime import UTC, date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from sysbot_helper.cogs.countdown import (
    Countdown,
    CountdownSnapshot,
    parse_target_datetime,
)
from sysbot_helper.templates import TemplateEngine
from sysbot_helper.utils import LazyContext


class TestCountdownCog(unittest.TestCase):
    def test_countdown_snapshot_multi_year_humanize(self) -> None:
        # Famicom release: 1983-07-15 to 2026-08-28 -> 43 years, 1 month, 13 days
        reference = datetime(2026, 8, 28, 0, 0, 0, tzinfo=UTC)
        target = datetime(1983, 7, 15, 0, 0, 0, tzinfo=UTC)

        snapshot = CountdownSnapshot(target_datetime=target, reference_datetime=reference)

        self.assertTrue(snapshot.is_past)
        self.assertFalse(snapshot.is_future)
        self.assertEqual(snapshot.years, 43)
        self.assertEqual(snapshot.months, 1)
        self.assertEqual(snapshot.days, 13)
        self.assertEqual(snapshot.total_days, 15750)
        self.assertEqual(snapshot.humanize(), "43 years, 1 month, 13 days")
        self.assertEqual(str(snapshot), "43 years, 1 month, 13 days")
        self.assertEqual(snapshot.discord_relative, f"<t:{int(target.timestamp())}:R>")
        self.assertEqual(snapshot.discord_full, f"<t:{int(target.timestamp())}:F>")
        self.assertEqual(snapshot.discord_date, f"<t:{int(target.timestamp())}:d>")
        self.assertEqual(snapshot.discord_time, f"<t:{int(target.timestamp())}:t>")

    def test_countdown_snapshot_month_boundary_edge_case(self) -> None:
        # Jan 31 to March 1 (leap and non-leap years)
        jan31 = datetime(2026, 1, 31, 0, 0, 0, tzinfo=UTC)
        mar1 = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)

        snapshot = CountdownSnapshot(target_datetime=mar1, reference_datetime=jan31)
        self.assertGreaterEqual(snapshot.days, 0)
        self.assertEqual(snapshot.months, 1)
        self.assertEqual(snapshot.days, 1)
        self.assertEqual(snapshot.humanize(), "1 month, 1 day")

    def test_countdown_snapshot_short_duration_humanize(self) -> None:
        # Within the same day: 4 hours, 30 minutes, 45 seconds
        reference = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        target = datetime(2026, 1, 1, 14, 30, 45, tzinfo=UTC)

        snapshot = CountdownSnapshot(target_datetime=target, reference_datetime=reference)

        self.assertTrue(snapshot.is_future)
        self.assertFalse(snapshot.is_past)
        self.assertEqual(snapshot.years, 0)
        self.assertEqual(snapshot.months, 0)
        self.assertEqual(snapshot.days, 0)
        self.assertEqual(snapshot.hours, 4)
        self.assertEqual(snapshot.minutes, 30)
        self.assertEqual(snapshot.seconds, 45)
        self.assertEqual(snapshot.humanize(), "4 hours, 30 minutes, 45 seconds")

    def test_countdown_snapshot_clock_borrowing(self) -> None:
        # Test borrowing across seconds, minutes, and hours
        reference = datetime(2026, 1, 1, 10, 30, 45, tzinfo=UTC)
        target = datetime(2026, 1, 1, 12, 15, 10, tzinfo=UTC)

        snapshot = CountdownSnapshot(target_datetime=target, reference_datetime=reference)
        self.assertEqual(snapshot.hours, 1)
        self.assertEqual(snapshot.minutes, 44)
        self.assertEqual(snapshot.seconds, 25)
        self.assertEqual(snapshot.humanize(), "1 hour, 44 minutes, 25 seconds")

    def test_countdown_snapshot_month_borrowing(self) -> None:
        # 1989-04-21 to 2026-02-15 -> 36 years, 9 months, 25 days
        borrow_ref = datetime(2026, 2, 15, 0, 0, 0, tzinfo=UTC)
        borrow_target = datetime(1989, 4, 21, 0, 0, 0, tzinfo=UTC)
        borrow_snapshot = CountdownSnapshot(target_datetime=borrow_target, reference_datetime=borrow_ref)

        self.assertEqual(borrow_snapshot.years, 36)
        self.assertEqual(borrow_snapshot.months, 9)
        self.assertEqual(borrow_snapshot.days, 25)
        self.assertEqual(borrow_snapshot.humanize(), "36 years, 9 months, 25 days")

    def test_countdown_snapshot_singular_units(self) -> None:
        singular_ref = datetime(2026, 3, 2, 0, 0, 0, tzinfo=UTC)
        singular_target = datetime(2025, 2, 1, 0, 0, 0, tzinfo=UTC)
        singular_snapshot = CountdownSnapshot(target_datetime=singular_target, reference_datetime=singular_ref)
        self.assertEqual(singular_snapshot.humanize(), "1 year, 1 month, 1 day")

    def test_countdown_snapshot_cross_timezone(self) -> None:
        # Tokyo time (UTC+9) vs UTC
        tokyo_time = datetime(2026, 1, 1, 9, 0, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        utc_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        snapshot = CountdownSnapshot(target_datetime=tokyo_time, reference_datetime=utc_time)
        self.assertEqual(snapshot.total_seconds, 0)
        self.assertEqual(snapshot.humanize(), "0 seconds")

    def test_countdown_snapshot_zero_duration(self) -> None:
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        snapshot = CountdownSnapshot(target_datetime=now, reference_datetime=now)

        self.assertFalse(snapshot.is_future)
        self.assertFalse(snapshot.is_past)
        self.assertEqual(snapshot.years, 0)
        self.assertEqual(snapshot.months, 0)
        self.assertEqual(snapshot.days, 0)
        self.assertEqual(snapshot.hours, 0)
        self.assertEqual(snapshot.minutes, 0)
        self.assertEqual(snapshot.seconds, 0)
        self.assertEqual(snapshot.total_seconds, 0)
        self.assertEqual(snapshot.humanize(), "0 seconds")

    def test_parse_target_datetime_various_types(self) -> None:
        # ISO string with UTC 'Z'
        utc_target = parse_target_datetime("2026-12-31T23:59:59Z", "UTC")
        self.assertEqual(utc_target.year, 2026)
        self.assertEqual(utc_target.tzinfo, UTC)

        # Naive ISO string defaults to default timezone
        naive_target = parse_target_datetime("2026-06-01 15:00:00", "Europe/Berlin")
        self.assertEqual(naive_target.tzinfo, ZoneInfo("Europe/Berlin"))

        # Naive datetime object
        naive_dt = parse_target_datetime(datetime(2026, 6, 1, 12, 0, 0), "Europe/Berlin")
        self.assertEqual(naive_dt.tzinfo, ZoneInfo("Europe/Berlin"))

        # Aware datetime object
        aware_dt = parse_target_datetime(datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC), "Europe/Berlin")
        self.assertEqual(aware_dt.tzinfo, UTC)

        # date object
        date_target = parse_target_datetime(date(2026, 7, 1), "UTC")
        self.assertEqual(date_target.year, 2026)
        self.assertEqual(date_target.month, 7)
        self.assertEqual(date_target.day, 1)

        # Unix integer timestamp
        timestamp_target = parse_target_datetime(1767225600, "UTC")
        self.assertEqual(int(timestamp_target.timestamp()), 1767225600)

        # String digit timestamp
        digit_string_target = parse_target_datetime("1767225600", "UTC")
        self.assertEqual(int(digit_string_target.timestamp()), 1767225600)

        # Negative (pre-1970) timestamp
        pre_1970_target = parse_target_datetime("-1000000", "UTC")
        self.assertEqual(int(pre_1970_target.timestamp()), -1000000)

        # Float timestamp string
        float_target = parse_target_datetime("1767225600.5", "UTC")
        self.assertEqual(int(float_target.timestamp()), 1767225600)

    def test_countdown_config_validation(self) -> None:
        valid_config = Countdown.Config(
            default_timezone="Asia/Tokyo",
            events={"launch": "2026-01-01T00:00:00Z"},
        )
        self.assertEqual(valid_config.default_timezone, "Asia/Tokyo")

        with self.assertRaises(ValueError):
            Countdown.Config(default_timezone="Invalid/Timezone_Name")

        with self.assertRaises(ValueError):
            Countdown.Config(events={"bad_event": "not-a-valid-date"})

    def test_template_rendering_integration(self) -> None:
        mock_bot = MagicMock()
        mock_bot.guild_config.return_value = {"timezone": "UTC"}

        config = Countdown.Config(
            default_timezone="UTC",
            events={
                "new_year": "2099-01-01T00:00:00Z",
                "launch": "2020-01-01T00:00:00Z",
            },
        )
        cog = Countdown(mock_bot, config)

        mock_context = MagicMock()
        mock_context.guild = MagicMock()

        variables_map = cog.template_variables(mock_context)
        lazy_countdown = LazyContext(variables_map)
        template_variables = {"countdown": lazy_countdown}

        template_engine = TemplateEngine()

        # Test default string render uses humanize directly
        rendered_str = template_engine.render_string("{{ countdown.launch }}", template_variables)
        self.assertIn("years", rendered_str)

        # Test properties
        rendered_future = template_engine.render_string("{{ countdown.new_year.is_future }}", template_variables)
        self.assertEqual(rendered_future, "True")

        rendered_past = template_engine.render_string("{{ countdown.launch.is_past }}", template_variables)
        self.assertEqual(rendered_past, "True")

        # Test discord timestamp
        rendered_discord = template_engine.render_string(
            "{{ countdown.new_year.discord_relative }}",
            template_variables,
        )
        self.assertTrue(rendered_discord.startswith("<t:") and rendered_discord.endswith(":R>"))
