import unittest
from datetime import datetime
from sysbot_helper.cron import CronItem, CronExpression


class TestCronExpression(unittest.TestCase):
    def test_cron_item_wildcard_matching(self) -> None:
        """Verifies that a wildcard cron item matches any integer value within bounds."""
        cron_item: CronItem = CronItem.Minute("*")

        self.assertTrue(cron_item.match(0))
        self.assertTrue(cron_item.match(30))
        self.assertTrue(cron_item.match(59))

    def test_cron_item_range_and_interval_matching(self) -> None:
        """Verifies range with interval step evaluation."""
        cron_item: CronItem = CronItem.Hour("2-10/2")

        # Range is 2 to 10 with interval 2: expected matching hours are 2, 4, 6, 8, 10
        self.assertTrue(cron_item.match(2))
        self.assertTrue(cron_item.match(4))
        self.assertFalse(cron_item.match(3))
        self.assertFalse(cron_item.match(12))

    def test_cron_expression_is_now_evaluation(self) -> None:
        """Verifies datetime matching against full five-field cron expressions."""
        cron_expression: CronExpression = CronExpression("15 14 1 7 *")

        # 2026-07-01 14:15:00 matches minute 15, hour 14, day 1, month 7
        target_datetime: datetime = datetime(2026, 7, 1, 14, 15, 0)
        non_matching_datetime: datetime = datetime(2026, 7, 1, 14, 16, 0)

        self.assertTrue(cron_expression.is_now(target_datetime))
        self.assertFalse(cron_expression.is_now(non_matching_datetime))

    def test_invalid_cron_interval_raises_value_error(self) -> None:
        """Verifies that non-numeric or negative intervals raise a ValueError."""
        with self.assertRaises(ValueError):
            CronItem.Minute("*/invalid")

        with self.assertRaises(ValueError):
            CronItem.Minute("*/0")
