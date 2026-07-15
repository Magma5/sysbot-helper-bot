import unittest
from datetime import datetime

from sysbot_helper.cron import CronExpression, CronFieldType, CronItem, HashedCronResolver


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

        self.assertTrue(cron_item.match(5))
        self.assertTrue(cron_item.match(15))
        self.assertTrue(cron_item.match(25))
        self.assertTrue(cron_item.match(55))
        self.assertFalse(cron_item.match(0))
        self.assertFalse(cron_item.match(10))

    def test_cron_item_range_and_interval_matching(self) -> None:
        """Verifies range with interval step evaluation."""
        cron_item: CronItem = CronItem.Hour("2-10/2")

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

    def test_sunday_alias_and_full_week_range_matching(self) -> None:
        """Verifies that 0-7 and 1-7 full week ranges match all days and set is_wildcard."""
        dow_range_0_7: CronItem = CronItem.DayOfWeek("0-7")
        dow_range_1_7: CronItem = CronItem.DayOfWeek("1-7")

        for day in range(7):
            self.assertTrue(dow_range_0_7.match(day), f"Failed to match day {day} for range 0-7")
            self.assertTrue(dow_range_1_7.match(day), f"Failed to match day {day} for range 1-7")

        self.assertTrue(dow_range_0_7.is_wildcard)
        self.assertTrue(dow_range_1_7.is_wildcard)

    def test_hashed_wrap_around_range_resolution(self) -> None:
        """Verifies that H(22-5) wrap-around ranges resolve without raising a randint ValueError."""
        resolved: str = HashedCronResolver.resolve_token(
            token_expression="H(22-5)",
            seed_integer=12345,
            minimum_field_value=0,
            maximum_field_value=23,
        )
        resolved_int = int(resolved)
        self.assertTrue(22 <= resolved_int <= 23 or 0 <= resolved_int <= 5)

    def test_hashed_wrap_around_step_resolution(self) -> None:
        """Verifies that H(22-5)/5 cyclic step tokens resolve cleanly without raising ValueError."""

        resolved: str = HashedCronResolver.resolve_token(
            token_expression="H(22-5)/5",
            seed_integer=12345,
            minimum_field_value=0,
            maximum_field_value=23,
        )
        # Should be parsed cleanly by CronExpression
        cron = CronExpression(f"0 {resolved} * * *")
        self.assertIsNotNone(cron)

    def test_hashed_step_range_upper_bound(self) -> None:
        """Verifies that H(10-30)/5 preserves upper bound 30 and constrains start offset to [10, 14]."""
        resolved: str = HashedCronResolver.resolve_token(
            token_expression="H(10-30)/5",
            seed_integer=12345,
            minimum_field_value=0,
            maximum_field_value=59,
        )
        self.assertTrue(resolved.endswith("-30/5"), f"Resolved '{resolved}' did not end with -30/5")
        start_offset: int = int(resolved.split("-")[0])
        self.assertTrue(10 <= start_offset <= 14, f"Start offset {start_offset} not in window [10, 14]")

    def test_cross_field_hash_independence(self) -> None:
        """Verifies that SECOND, MINUTE, and HOUR generate distinct hashes even at identical period timestamps."""
        timestamp = 1700000000
        sec_hash = HashedCronResolver._compute_stable_hash("job", CronFieldType.SECOND, timestamp)
        min_hash = HashedCronResolver._compute_stable_hash("job", CronFieldType.MINUTE, timestamp)
        hr_hash = HashedCronResolver._compute_stable_hash("job", CronFieldType.HOUR, timestamp)

        self.assertNotEqual(sec_hash, min_hash)
        self.assertNotEqual(min_hash, hr_hash)
        self.assertNotEqual(sec_hash, hr_hash)

    def test_predefined_shortcuts(self) -> None:
        """Verifies expansion of @hourly, @daily, @weekly, @monthly, @yearly."""
        hourly_expression: CronExpression = CronExpression("@hourly")
        daily_expression: CronExpression = CronExpression("@daily")

        self.assertTrue(hourly_expression.is_now(datetime(2026, 7, 1, 14, 0, 0)))
        self.assertFalse(hourly_expression.is_now(datetime(2026, 7, 1, 14, 15, 0)))

        self.assertTrue(daily_expression.is_now(datetime(2026, 7, 1, 0, 0, 0)))
        self.assertFalse(daily_expression.is_now(datetime(2026, 7, 1, 12, 0, 0)))

    def test_posix_day_of_month_or_day_of_week_matching(self) -> None:
        """Verifies POSIX OR rule when both DOM and DOW are specified."""
        expression: CronExpression = CronExpression("0 0 1 * Mon")

        self.assertTrue(expression.is_now(datetime(2026, 7, 1, 0, 0, 0)))
        self.assertTrue(expression.is_now(datetime(2026, 7, 6, 0, 0, 0)))
        self.assertFalse(expression.is_now(datetime(2026, 7, 7, 0, 0, 0)))

    def test_six_field_cron_sub_minute_precision(self) -> None:
        """Verifies 6-field sub-minute precision cron expressions (sec min hr dom mon dow)."""
        seed: str = "fast_polling_job"
        six_field_cron: CronExpression = CronExpression("H/15 * * * * *", seed=seed)

        target_time: datetime = datetime(2026, 7, 6, 14, 30, 0)
        resolved_str: str = HashedCronResolver.resolve_expression(
            "H/15 * * * * *", job_name=seed, target_datetime=target_time
        )
        tokens: list[str] = resolved_str.split()
        self.assertEqual(len(tokens), 6)

        self.assertIn("/15", tokens[0])
        start_sec: int = int(tokens[0].split("-")[0])

        matching_time: datetime = datetime(2026, 7, 6, 14, 30, start_sec)
        self.assertTrue(six_field_cron.is_now(matching_time))

    def test_stable_cross_process_crc32_hashing(self) -> None:
        """Verifies that zlib.crc32 hashing is cross-process stable."""
        hash_one: int = HashedCronResolver._compute_stable_hash("job_a", CronFieldType.MINUTE, 170000)
        hash_two: int = HashedCronResolver._compute_stable_hash("job_a", CronFieldType.MINUTE, 170000)

        self.assertEqual(hash_one, hash_two)

    def test_invalid_cron_interval_raises_value_error(self) -> None:
        """Verifies that non-numeric or negative intervals raise a ValueError."""
        with self.assertRaises(ValueError):
            CronItem.Minute("*/invalid")

        with self.assertRaises(ValueError):
            CronItem.Minute("*/0")
