import calendar
from datetime import datetime


_MONTH_NAMES: dict[str, int] = {
    name.lower(): index for index, name in enumerate(calendar.month_name) if name
} | {name.lower(): index for index, name in enumerate(calendar.month_abbr) if name}

_DAY_NAMES: dict[str, int] = {
    "sun": 0,
    "sunday": 0,
    "mon": 1,
    "monday": 1,
    "tue": 2,
    "tuesday": 2,
    "wed": 3,
    "wednesday": 3,
    "thu": 4,
    "thursday": 4,
    "fri": 5,
    "friday": 5,
    "sat": 6,
    "saturday": 6,
    "7": 0,  # Map 7 (Sunday) to 0 internally for consistency
}

_PREDEFINED_CRON_SHORTCUTS: dict[str, str] = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


class CronItem:
    """Representation of a single cron expression field (minute, hour, day, month, day-of-week)."""

    __slots__ = (
        "interval",
        "min_value",
        "max_value",
        "range_from",
        "range_to",
        "aliases",
        "is_day_of_week",
        "is_wildcard",
    )

    @classmethod
    def Second(cls, item_expression: str) -> "CronItem":
        return cls(item_expression, 0, 59)

    @classmethod
    def Minute(cls, item_expression: str) -> "CronItem":
        return cls(item_expression, 0, 59)

    @classmethod
    def Hour(cls, item_expression: str) -> "CronItem":
        return cls(item_expression, 0, 23)

    @classmethod
    def Day(cls, item_expression: str) -> "CronItem":
        return cls(item_expression, 1, 31)

    @classmethod
    def Month(cls, item_expression: str) -> "CronItem":
        return cls(item_expression, 1, 12, _MONTH_NAMES)

    @classmethod
    def DayOfWeek(cls, item_expression: str) -> "CronItem":
        return cls(item_expression, 0, 7, _DAY_NAMES, is_day_of_week=True)

    def __init__(
        self,
        item_expression: str,
        min_value: int,
        max_value: int,
        aliases: dict[str, int] | None = None,
        is_day_of_week: bool = False,
    ) -> None:
        self.interval: int = 1
        self.min_value: int = min_value
        self.max_value: int = max_value
        self.range_from: int = min_value
        self.range_to: int = max_value
        self.aliases: dict[str, int] = {
            name.lower(): number for name, number in (aliases or {}).items()
        }
        self.is_day_of_week: bool = is_day_of_week
        self.is_wildcard: bool = False

        self._parse(item_expression)

    def match(self, current_value: int) -> bool:
        """Evaluates whether current_value matches the cron item range and step interval."""
        target_value: int = current_value
        range_start: int = self.range_from
        range_end: int = self.range_to

        if self.is_day_of_week:
            # 0 and 7 both represent Sunday in cron standard
            if target_value == 7:
                target_value = 0

            # Full week wildcard or full 0-7 range matches any day
            if range_start == 0 and range_end >= 6:
                return (target_value - range_start) % self.interval == 0

            normalized_start: int = 0 if range_start == 7 else range_start
            normalized_end: int = 0 if range_end == 7 else range_end

            if normalized_start <= normalized_end:
                return (
                    normalized_start <= target_value <= normalized_end
                    and (target_value - normalized_start) % self.interval == 0
                )

            # Wrap-around range (e.g. Fri-Mon -> 5-1)
            is_within_wrap_range = (target_value >= normalized_start) or (
                target_value <= normalized_end
            )
            return is_within_wrap_range and (
                (target_value - normalized_start) % self.interval == 0
            )

        is_within_range = range_start <= target_value <= range_end
        return is_within_range and ((target_value - range_start) % self.interval == 0)

    def _parse(self, item_expression: str) -> None:
        """Parses individual field expression, extracting range bounds and interval steps."""
        expression_to_parse: str = item_expression.strip()

        if "/" in expression_to_parse:
            expression_to_parse, interval_string = expression_to_parse.split("/", 1)
            if not interval_string.isdigit():
                raise ValueError(
                    f"Invalid interval step '{interval_string}' in expression '{item_expression}'"
                )
            self.interval = int(interval_string)
            if self.interval < 1:
                raise ValueError(
                    f"Interval step must be >= 1 in expression '{item_expression}'"
                )

        if expression_to_parse == "*":
            self.is_wildcard = self.interval == 1
            self.range_from = self.min_value
            self.range_to = self.max_value
        elif "-" in expression_to_parse:
            range_from_string, range_to_string = expression_to_parse.split("-", 1)
            self.range_from = (
                self._validate_and_convert_value(range_from_string)
                if range_from_string.strip()
                else self.min_value
            )
            self.range_to = (
                self._validate_and_convert_value(range_to_string)
                if range_to_string.strip()
                else self.max_value
            )
        else:
            start_value: int = self._validate_and_convert_value(expression_to_parse)
            self.range_from = start_value
            # If step / is specified without explicit hyphen range (e.g. 5/10), range_to defaults to max_value
            if self.interval > 1:
                self.range_to = self.max_value
            else:
                self.range_to = start_value

        if self.range_from > self.range_to and not self.is_day_of_week:
            raise ValueError(
                f"Invalid range bounds: {self.range_from}-{self.range_to} in '{item_expression}'"
            )

    def _validate_and_convert_value(self, value_string: str) -> int:
        """Converts string value or alias to integer and validates range limits."""
        cleaned_value_string: str = value_string.lower()

        if cleaned_value_string in self.aliases:
            integer_value: int = self.aliases[cleaned_value_string]
        elif cleaned_value_string.isdigit():
            integer_value = int(cleaned_value_string)
        else:
            raise ValueError(f"Invalid integer value or alias: '{value_string}'")

        if integer_value < self.min_value or (
            self.max_value is not None and integer_value > self.max_value
        ):
            raise ValueError(
                f"Value '{integer_value}' out of allowed bounds [{self.min_value}, {self.max_value}]"
            )

        return integer_value

    def __str__(self) -> str:
        """Normalizes the cron item into string format."""
        if self.range_from == self.min_value and self.range_to == self.max_value:
            pattern_string: str = "*"
        elif self.range_from == self.range_to:
            pattern_string = f"{self.range_from}"
        else:
            pattern_string = f"{self.range_from}-{self.range_to}"

        if self.interval != 1:
            return f"{pattern_string}/{self.interval}"

        return pattern_string


class CronExpression:
    """Representation of a standard 5-field cron expression with POSIX compliance."""

    __slots__ = ("minute", "hour", "day", "month", "day_of_week", "raw_expression")

    def __init__(self, expression_string: str) -> None:
        self.raw_expression: str = expression_string.strip()

        # Expand predefined shortcuts (e.g. @daily, @hourly)
        normalized_expression: str = _PREDEFINED_CRON_SHORTCUTS.get(
            self.raw_expression.lower(),
            self.raw_expression,
        )

        expression_tokens: list[str] = normalized_expression.split()
        if len(expression_tokens) < 5:
            raise ValueError(
                f"Cron expression requires 5 fields, received {len(expression_tokens)}: '{expression_string}'"
            )

        minute_token, hour_token, day_token, month_token, day_of_week_token = (
            expression_tokens[:5]
        )

        self.minute: list[CronItem] = [
            CronItem.Minute(sub_token) for sub_token in minute_token.split(",")
        ]
        self.hour: list[CronItem] = [
            CronItem.Hour(sub_token) for sub_token in hour_token.split(",")
        ]
        self.day: list[CronItem] = [
            CronItem.Day(sub_token) for sub_token in day_token.split(",")
        ]
        self.month: list[CronItem] = [
            CronItem.Month(sub_token) for sub_token in month_token.split(",")
        ]
        self.day_of_week: list[CronItem] = [
            CronItem.DayOfWeek(sub_token) for sub_token in day_of_week_token.split(",")
        ]

    def is_now(self, target_datetime: datetime | None = None) -> bool:
        """Evaluates whether target_datetime matches the cron expression."""
        if target_datetime is None:
            target_datetime = datetime.now()

        # Python dt.weekday(): 0 = Monday, 6 = Sunday
        # Standard cron day_of_week: 0 = Sunday, 1 = Monday, ..., 6 = Saturday
        current_day_of_week: int = (target_datetime.weekday() + 1) % 7

        minute_match: bool = any(
            item.match(target_datetime.minute) for item in self.minute
        )
        hour_match: bool = any(item.match(target_datetime.hour) for item in self.hour)
        month_match: bool = any(
            item.match(target_datetime.month) for item in self.month
        )

        day_of_month_match: bool = any(
            item.match(target_datetime.day) for item in self.day
        )
        day_of_week_match: bool = any(
            item.match(current_day_of_week) for item in self.day_of_week
        )

        # Check POSIX rule: if both DOM and DOW are restricted (not *), use OR logic. Otherwise use AND logic.
        day_of_month_restricted: bool = not any(item.is_wildcard for item in self.day)
        day_of_week_restricted: bool = not any(
            item.is_wildcard for item in self.day_of_week
        )

        if day_of_month_restricted and day_of_week_restricted:
            date_match: bool = day_of_month_match or day_of_week_match
        else:
            date_match: bool = day_of_month_match and day_of_week_match

        return minute_match and hour_match and month_match and date_match

    def __str__(self) -> str:
        return " ".join(
            ",".join(str(item) for item in cron_field_items)
            for cron_field_items in (
                self.minute,
                self.hour,
                self.day,
                self.month,
                self.day_of_week,
            )
        )
