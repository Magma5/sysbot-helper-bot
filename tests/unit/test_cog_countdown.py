import unittest
from datetime import UTC, date, datetime, time
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from sysbot_helper.cogs.countdown import (
    AnnualRecurrence,
    Countdown,
    CountdownSnapshot,
    _has_explicit_time_component,
    parse_event_target,
    parse_target_datetime,
)
from sysbot_helper.templates import TemplateEngine
from sysbot_helper.utils import LazyContext


class TestCountdownCog(unittest.TestCase):
    def test_countdown_snapshot_multi_year_humanize(self) -> None:
        # Famicom release: 1983-07-15 to 2026-08-28 -> 43 years, 1 month, 13 days
        reference = datetime(2026, 8, 28, 0, 0, 0, tzinfo=UTC)
        target = datetime(1983, 7, 15, 0, 0, 0, tzinfo=UTC)

        snapshot = CountdownSnapshot(target_datetime=target, reference_datetime=reference, has_explicit_time=False)

        self.assertTrue(snapshot.is_past)
        self.assertFalse(snapshot.is_future)
        self.assertFalse(snapshot.is_today)
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

    def test_countdown_snapshot_next_anniversary(self) -> None:
        # Famicom (1983-07-15) evaluated on 2026-08-28 -> next anniversary is 2027-07-15 (44th anniversary)
        reference = datetime(2026, 8, 28, 0, 0, 0, tzinfo=UTC)
        target = datetime(1983, 7, 15, 0, 0, 0, tzinfo=UTC)
        snapshot = CountdownSnapshot(target_datetime=target, reference_datetime=reference, has_explicit_time=False)

        next_anniversary = snapshot.next_anniversary
        self.assertTrue(next_anniversary.is_future)
        self.assertEqual(next_anniversary.target_datetime.year, 2027)
        self.assertEqual(next_anniversary.target_datetime.month, 7)
        self.assertEqual(next_anniversary.target_datetime.day, 15)
        self.assertEqual(snapshot.next_anniversary_ordinal, 44)

    def test_annual_recurrence_day_of_event_active_window(self) -> None:
        # Christmas evaluated on Dec 25 at 14:30 -> remains active (0 days)
        christmas = AnnualRecurrence(month=12, day=25)
        dec25_afternoon = datetime(2026, 12, 25, 14, 30, 0, tzinfo=UTC)

        target_on_christmas = christmas.calculate_next_occurrence(dec25_afternoon)
        self.assertEqual(target_on_christmas, datetime(2026, 12, 25, 0, 0, 0, tzinfo=UTC))

        snapshot_on_christmas = CountdownSnapshot(
            target_datetime=target_on_christmas,
            reference_datetime=dec25_afternoon,
            has_explicit_time=False,
        )
        self.assertTrue(snapshot_on_christmas.is_today)
        self.assertFalse(snapshot_on_christmas.is_past)
        self.assertFalse(snapshot_on_christmas.is_future)
        self.assertEqual(snapshot_on_christmas.humanize(), "0 days")
        self.assertEqual(str(snapshot_on_christmas), "0 days")

        # Christmas evaluated on Dec 26 at 00:00:01 -> rolls over to next year (2027-12-25)
        dec26_morning = datetime(2026, 12, 26, 0, 0, 1, tzinfo=UTC)
        target_after_christmas = christmas.calculate_next_occurrence(dec26_morning)
        self.assertEqual(target_after_christmas, datetime(2027, 12, 25, 0, 0, 0, tzinfo=UTC))

        snapshot_after_christmas = CountdownSnapshot(
            target_datetime=target_after_christmas,
            reference_datetime=dec26_morning,
            has_explicit_time=False,
        )
        self.assertFalse(snapshot_after_christmas.is_today)
        self.assertTrue(snapshot_after_christmas.is_future)
        self.assertIn("months", snapshot_after_christmas.humanize())

    def test_historical_anniversary_day_of_event(self) -> None:
        # Famicom (1983-07-15) evaluated on July 15, 2026 at 12:00:00
        famicom_target = datetime(1983, 7, 15, 0, 0, 0, tzinfo=UTC)
        anniversary_day = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)

        snapshot = CountdownSnapshot(
            target_datetime=famicom_target,
            reference_datetime=anniversary_day,
            has_explicit_time=False,
        )
        self.assertEqual(snapshot.years, 43)
        self.assertEqual(snapshot.months, 0)
        self.assertEqual(snapshot.days, 0)
        self.assertEqual(snapshot.humanize(), "43 years")

        # Next anniversary on the day of event stays on today and displays '0 days'
        next_anniversary = snapshot.next_anniversary
        self.assertTrue(next_anniversary.is_today)
        self.assertEqual(next_anniversary.target_datetime.year, 2026)
        self.assertEqual(next_anniversary.humanize(), "0 days")
        self.assertEqual(snapshot.next_anniversary_ordinal, 43)

    def test_explicit_timestamp_sub_day_precision(self) -> None:
        # Event with explicit timestamp: 2026-12-25 15:30:00 UTC evaluated at 12:00:00 UTC
        target = datetime(2026, 12, 25, 15, 30, 0, tzinfo=UTC)
        reference = datetime(2026, 12, 25, 12, 0, 0, tzinfo=UTC)

        snapshot = CountdownSnapshot(target_datetime=target, reference_datetime=reference, has_explicit_time=True)
        self.assertTrue(snapshot.is_today)
        self.assertTrue(snapshot.is_future)
        self.assertEqual(snapshot.hours, 3)
        self.assertEqual(snapshot.minutes, 30)
        self.assertEqual(snapshot.humanize(), "3 hours, 30 minutes")

    def test_annual_recurrence_with_explicit_time(self) -> None:
        # Annual event with specific time of day: 12-25 at 14:30:00
        event = AnnualRecurrence(month=12, day=25, time_of_day=time(14, 30, 0))
        self.assertTrue(event.has_explicit_time)

        # Before time on same day -> targets today
        ref_before = datetime(2026, 12, 25, 10, 0, 0, tzinfo=UTC)
        next_dt_before = event.calculate_next_occurrence(ref_before)
        self.assertEqual(next_dt_before, datetime(2026, 12, 25, 14, 30, 0, tzinfo=UTC))

        # After time on same day -> rolls over to next year
        ref_after = datetime(2026, 12, 25, 15, 0, 0, tzinfo=UTC)
        next_dt_after = event.calculate_next_occurrence(ref_after)
        self.assertEqual(next_dt_after, datetime(2027, 12, 25, 14, 30, 0, tzinfo=UTC))

    def test_has_explicit_time_component_detection(self) -> None:
        self.assertTrue(_has_explicit_time_component(datetime(2026, 1, 1, 12, 0)))
        self.assertFalse(_has_explicit_time_component(date(2026, 1, 1)))
        self.assertTrue(_has_explicit_time_component(1767225600))
        self.assertTrue(_has_explicit_time_component(1767225600.5))
        self.assertTrue(_has_explicit_time_component("1767225600"))
        self.assertTrue(_has_explicit_time_component("2026-12-25T14:30:00"))
        self.assertTrue(_has_explicit_time_component("2026-12-25 14:30:00"))
        self.assertFalse(_has_explicit_time_component("2026-12-25"))
        self.assertFalse(_has_explicit_time_component("12-25"))

    def test_annual_recurrence_leap_day(self) -> None:
        # Leap day event (Feb 29) evaluated in 2025 (non-leap) -> advances to 2028 (leap year)
        reference = datetime(2025, 6, 1, 0, 0, 0, tzinfo=UTC)
        leap_event = AnnualRecurrence(month=2, day=29)
        next_leap = leap_event.calculate_next_occurrence(reference)
        self.assertEqual(next_leap, datetime(2028, 2, 29, 0, 0, 0, tzinfo=UTC))

    def test_parse_event_target_formats(self) -> None:
        # Annual recurring format without time
        recurrence_1 = parse_event_target("12-25")
        self.assertIsInstance(recurrence_1, AnnualRecurrence)
        self.assertEqual(recurrence_1.month, 12)
        self.assertEqual(recurrence_1.day, 25)
        self.assertIsNone(recurrence_1.time_of_day)

        # Annual recurring format with explicit time
        recurrence_with_time = parse_event_target("12-25T14:30:00")
        self.assertIsInstance(recurrence_with_time, AnnualRecurrence)
        self.assertEqual(recurrence_with_time.month, 12)
        self.assertEqual(recurrence_with_time.day, 25)
        self.assertEqual(recurrence_with_time.time_of_day, time(14, 30, 0))

        recurrence_space = parse_event_target("12-25 14:30:00")
        self.assertEqual(recurrence_space.time_of_day, time(14, 30, 0))

        recurrence_2 = parse_event_target("--01-01")
        self.assertIsInstance(recurrence_2, AnnualRecurrence)
        self.assertEqual(recurrence_2.month, 1)
        self.assertEqual(recurrence_2.day, 1)

        # Invalid annual formats raise ValueError
        with self.assertRaises(ValueError):
            parse_event_target("13-40")

        with self.assertRaises(ValueError):
            parse_event_target("invalid-format")

        # Standard fixed datetime
        fixed_dt = parse_event_target("1983-07-15", "Asia/Tokyo")
        self.assertIsInstance(fixed_dt, datetime)
        self.assertEqual(fixed_dt.year, 1983)
        self.assertEqual(fixed_dt.tzinfo, ZoneInfo("Asia/Tokyo"))

    def test_countdown_snapshot_month_boundary_edge_case(self) -> None:
        # Jan 31 to March 1
        jan31 = datetime(2026, 1, 31, 0, 0, 0, tzinfo=UTC)
        mar1 = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)

        snapshot = CountdownSnapshot(target_datetime=mar1, reference_datetime=jan31, has_explicit_time=False)
        self.assertGreaterEqual(snapshot.days, 0)
        self.assertEqual(snapshot.months, 1)
        self.assertEqual(snapshot.days, 1)
        self.assertEqual(snapshot.humanize(), "1 month, 1 day")

    def test_countdown_snapshot_clock_borrowing(self) -> None:
        reference = datetime(2026, 1, 1, 10, 30, 45, tzinfo=UTC)
        target = datetime(2026, 1, 1, 12, 15, 10, tzinfo=UTC)

        snapshot = CountdownSnapshot(target_datetime=target, reference_datetime=reference, has_explicit_time=True)
        self.assertEqual(snapshot.hours, 1)
        self.assertEqual(snapshot.minutes, 44)
        self.assertEqual(snapshot.seconds, 25)
        self.assertEqual(snapshot.humanize(), "1 hour, 44 minutes, 25 seconds")

    def test_countdown_snapshot_month_borrowing(self) -> None:
        borrow_ref = datetime(2026, 2, 15, 0, 0, 0, tzinfo=UTC)
        borrow_target = datetime(1989, 4, 21, 0, 0, 0, tzinfo=UTC)
        borrow_snapshot = CountdownSnapshot(
            target_datetime=borrow_target, reference_datetime=borrow_ref, has_explicit_time=False
        )

        self.assertEqual(borrow_snapshot.years, 36)
        self.assertEqual(borrow_snapshot.months, 9)
        self.assertEqual(borrow_snapshot.days, 25)
        self.assertEqual(borrow_snapshot.humanize(), "36 years, 9 months, 25 days")

    def test_countdown_snapshot_singular_units(self) -> None:
        singular_ref = datetime(2026, 3, 2, 0, 0, 0, tzinfo=UTC)
        singular_target = datetime(2025, 2, 1, 0, 0, 0, tzinfo=UTC)
        singular_snapshot = CountdownSnapshot(
            target_datetime=singular_target, reference_datetime=singular_ref, has_explicit_time=False
        )
        self.assertEqual(singular_snapshot.humanize(), "1 year, 1 month, 1 day")

    def test_countdown_snapshot_cross_timezone(self) -> None:
        tokyo_time = datetime(2026, 1, 1, 9, 0, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        utc_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        snapshot = CountdownSnapshot(target_datetime=tokyo_time, reference_datetime=utc_time, has_explicit_time=True)
        self.assertEqual(snapshot.total_seconds, 0)
        self.assertEqual(snapshot.humanize(), "0 seconds")

    def test_countdown_snapshot_zero_duration(self) -> None:
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        snapshot = CountdownSnapshot(target_datetime=now, reference_datetime=now, has_explicit_time=True)

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
        utc_target = parse_target_datetime("2026-12-31T23:59:59Z", "UTC")
        self.assertEqual(utc_target.year, 2026)
        self.assertEqual(utc_target.tzinfo, UTC)

        naive_target = parse_target_datetime("2026-06-01 15:00:00", "Europe/Berlin")
        self.assertEqual(naive_target.tzinfo, ZoneInfo("Europe/Berlin"))

        naive_dt = parse_target_datetime(datetime(2026, 6, 1, 12, 0, 0), "Europe/Berlin")
        self.assertEqual(naive_dt.tzinfo, ZoneInfo("Europe/Berlin"))

        aware_dt = parse_target_datetime(datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC), "Europe/Berlin")
        self.assertEqual(aware_dt.tzinfo, UTC)

        date_target = parse_target_datetime(date(2026, 7, 1), "UTC")
        self.assertEqual(date_target.year, 2026)
        self.assertEqual(date_target.month, 7)
        self.assertEqual(date_target.day, 1)

        timestamp_target = parse_target_datetime(1767225600, "UTC")
        self.assertEqual(int(timestamp_target.timestamp()), 1767225600)

        digit_string_target = parse_target_datetime("1767225600", "UTC")
        self.assertEqual(int(digit_string_target.timestamp()), 1767225600)

        pre_1970_target = parse_target_datetime("-1000000", "UTC")
        self.assertEqual(int(pre_1970_target.timestamp()), -1000000)

        float_target = parse_target_datetime("1767225600.5", "UTC")
        self.assertEqual(int(float_target.timestamp()), 1767225600)

    def test_countdown_config_validation(self) -> None:
        valid_config = Countdown.Config(
            default_timezone="Asia/Tokyo",
            events={
                "launch": "2026-01-01T00:00:00Z",
                "annual_new_year": "01-01",
            },
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
                "annual_christmas": "12-25",
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

        # Test historical countup
        rendered_str = template_engine.render_string("{{ countdown.launch }}", template_variables)
        self.assertIn("years", rendered_str)

        # Test annual recurring event rendered as string
        rendered_christmas = template_engine.render_string("{{ countdown.annual_christmas }}", template_variables)
        self.assertTrue(len(rendered_christmas) > 0)

        # Test next anniversary property
        rendered_anniversary = template_engine.render_string(
            "{{ countdown.launch.next_anniversary.is_future }}",
            template_variables,
        )
        self.assertEqual(rendered_anniversary, "True")
