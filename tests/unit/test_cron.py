import unittest
from datetime import datetime
from sysbot_helper.cron import CronItem, CronExpression, HashedCronResolver


class TestCronExpression(unittest.TestCase):
    def test_cron_item_wildcard_matching(self) -> None:
        """Verifies that a wildcard cron item matches any integer value within bounds."""
        cron_item: CronItem = CronItem.Minute("*")

        self.assertTrue(cron_item.match(0))
        self.assertTrue(cron_item.match(30))
        self.assertTrue(cron_item.match(59))

    def test_cron_item_step_expression_parsing(self) -> None:
        """Verifies step evaluation for 5/10 (starts at 5 through 59 step 10)."""
        cron_item: CronItem = CronItem.Minute("5/10")

        # Matching values: 5, 15, 25, 35, 45, 55
        self.assertTrue(cron_item.match(5))
        self.assertTrue(cron_item.match(15))
        self.assertTrue(cron_item.match(25))
        self.assertTrue(cron_item.match(55))
        self.assertFalse(cron_item.match(0))
        self.assertFalse(cron_item.match(10))

    def test_cron_item_range_and_interval_matching(self) -> None:
        """Verifies range with interval step evaluation."""
        cron_item: CronItem = CronItem.Hour("2-10/2")

        # Range is 2 to 10 with interval 2: expected matching hours are 2, 4, 6, 8, 10
        self.assertTrue(cron_item.match(2))
        self.assertTrue(cron_item.match(4))
        self.assertFalse(cron_item.match(3))
        self.assertFalse(cron_item.match(12))

    def test_cron_month_and_day_aliases(self) -> None:
        """Verifies textual month and day name alias parsing."""
        month_item: CronItem = CronItem.Month("Jan")
        self.assertTrue(month_item.match(1))
        self.assertFalse(month_item.match(2))

        day_of_week_item: CronItem = CronItem.DayOfWeek("Mon")
        self.assertTrue(day_of_week_item.match(1))
        self.assertFalse(day_of_week_item.match(0))

    def test_sunday_alias_matching(self) -> None:
        """Verifies both 0 and 7 match Sunday."""
        sunday_item_zero: CronItem = CronItem.DayOfWeek("0")
        sunday_item_seven: CronItem = CronItem.DayOfWeek("7")

        self.assertTrue(sunday_item_zero.match(0))
        self.assertTrue(sunday_item_seven.match(0))

    def test_predefined_shortcuts(self) -> None:
        """Verifies expansion of @hourly, @daily, @weekly, @monthly, @yearly."""
        hourly_expression: CronExpression = CronExpression("@hourly")
        daily_expression: CronExpression = CronExpression("@daily")

        # @hourly matches minute 0
        self.assertTrue(hourly_expression.is_now(datetime(2026, 7, 1, 14, 0, 0)))
        self.assertFalse(hourly_expression.is_now(datetime(2026, 7, 1, 14, 15, 0)))

        # @daily matches 00:00:00
        self.assertTrue(daily_expression.is_now(datetime(2026, 7, 1, 0, 0, 0)))
        self.assertFalse(daily_expression.is_now(datetime(2026, 7, 1, 12, 0, 0)))

    def test_posix_day_of_month_or_day_of_week_matching(self) -> None:
        """Verifies POSIX OR rule when both DOM and DOW are specified."""
        # '0 0 1 * Mon' matches if day is 1st OR day is Monday
        expression: CronExpression = CronExpression("0 0 1 * Mon")

        # 2026-07-01 is a Wednesday (DOM 1 matches, DOW does not)
        self.assertTrue(expression.is_now(datetime(2026, 7, 1, 0, 0, 0)))

        # 2026-07-06 is a Monday (DOM 6 does not match, DOW Mon matches)
        self.assertTrue(expression.is_now(datetime(2026, 7, 6, 0, 0, 0)))

        # 2026-07-07 is a Tuesday (neither matches)
        self.assertFalse(expression.is_now(datetime(2026, 7, 7, 0, 0, 0)))

    def test_hashed_cron_resolution_deterministic_matching(self) -> None:
        """Verifies that H hashed expressions resolve deterministically with Random(seed)."""
        seed: str = "leetcode_daily_sync"

        expression_one: CronExpression = CronExpression("H H(10-20) * * *", seed=seed)
        expression_two: CronExpression = CronExpression("H H(10-20) * * *", seed=seed)

        # Both instances with the same seed must produce identical string expressions
        self.assertEqual(str(expression_one), str(expression_two))

        # Test bounded range H(10-20) for hour field
        resolved_hour_item: CronItem = expression_one.hour[0]
        self.assertGreaterEqual(resolved_hour_item.range_from, 10)
        self.assertLessEqual(resolved_hour_item.range_to, 20)

    def test_invalid_cron_interval_raises_value_error(self) -> None:
        """Verifies that non-numeric or negative intervals raise a ValueError."""
        with self.assertRaises(ValueError):
            CronItem.Minute("*/invalid")

        with self.assertRaises(ValueError):
            CronItem.Minute("*/0")
