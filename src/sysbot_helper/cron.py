import calendar
import re
import zlib
from datetime import datetime, timedelta
from enum import Enum, auto
from random import Random
from typing import Any


class CronFieldType(Enum):
    """Enumeration of cron expression fields in order of granularity."""

    SECOND = auto()
    MINUTE = auto()
    HOUR = auto()
    DAY_OF_MONTH = auto()
    MONTH = auto()
    DAY_OF_WEEK = auto()


_MONTH_NAMES: dict[str, int] = {name.lower(): index for index, name in enumerate(calendar.month_name) if name} | {
    name.lower(): index for index, name in enumerate(calendar.month_abbr) if name
}

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


class HashedCronResolver:
    """Resolves 'H' hashed tokens deterministically using process-independent zlib.crc32 hashing."""

    HASH_TOKEN_PATTERN: re.Pattern[str] = re.compile(
        r"^H(?:\((?P<range_start>[0-9a-z]+)-(?P<range_end>[0-9a-z]+)\))?$",
        re.IGNORECASE,
    )

    # Specification defining allowed boundaries and alias mapping per cron field type
    FIELD_SPECIFICATIONS: list[tuple[CronFieldType, int, int, dict[str, int]]] = [
        (CronFieldType.SECOND, 0, 59, {}),
        (CronFieldType.MINUTE, 0, 59, {}),
        (CronFieldType.HOUR, 0, 23, {}),
        (CronFieldType.DAY_OF_MONTH, 1, 31, {}),
        (CronFieldType.MONTH, 1, 12, _MONTH_NAMES),
        (CronFieldType.DAY_OF_WEEK, 0, 7, _DAY_NAMES),
    ]

    @classmethod
    def resolve_expression(
        cls,
        expression_string: str,
        job_name: Any | None = None,
        target_datetime: datetime | None = None,
    ) -> str:
        """Resolves all 'H' tokens in a 5-field or 6-field cron expression into numeric cron values.

        Example:
            - Input:  "H/15 H(10-30) * * *" (job_name="backup")
            - Output: "7-59/15 18 * * *"
        """
        normalized_expression: str = _PREDEFINED_CRON_SHORTCUTS.get(
            expression_string.strip().lower(),
            expression_string.strip(),
        )

        tokens: list[str] = normalized_expression.split()
        if len(tokens) < 5 or job_name is None:
            return normalized_expression

        # Standardize 5-field expressions to 6-field internally by prepending "0" for seconds
        is_five_field: bool = len(tokens) == 5
        if is_five_field:
            tokens = ["0"] + tokens

        if target_datetime is None:
            target_datetime = datetime.now()

        resolved_tokens: list[str] = []
        for index, (field_type, min_val, max_val, aliases) in enumerate(cls.FIELD_SPECIFICATIONS):
            token: str = tokens[index]
            period_start_timestamp: int = cls._get_period_start_timestamp(
                field_type=field_type,
                target_datetime=target_datetime,
            )

            combined_seed_integer: int = cls._compute_stable_hash(
                job_name=job_name,
                period_start_timestamp=period_start_timestamp,
            )

            resolved_token: str = cls.resolve_token(
                token_expression=token,
                seed_integer=combined_seed_integer,
                minimum_field_value=min_val,
                maximum_field_value=max_val,
                aliases=aliases,
            )
            resolved_tokens.append(resolved_token)

        resolved_tokens.extend(tokens[6:])

        # Strip prepended '0' if original expression was 5-field
        if is_five_field:
            resolved_tokens = resolved_tokens[1:]

        return " ".join(resolved_tokens)

    @classmethod
    def resolve_token(
        cls,
        token_expression: str,
        seed_integer: int,
        minimum_field_value: int,
        maximum_field_value: int,
        aliases: dict[str, int] | None = None,
    ) -> str:
        """Resolves a single token like 'H', 'H(10-30)', or 'H/15' into standard numeric cron syntax.

        Recursively resolves nested tokens:
            - Comma list: "H(0-15),H(30-45)" -> evaluates sub-tokens independently.
            - Step expression: "H/15" -> evaluates hashed start offset "7", returning "7-59/15".
            - Range token: "H(10-30)" -> picks deterministic integer between 10 and 30.
        """
        # Handle comma-separated lists recursively
        if "," in token_expression:
            sub_tokens: list[str] = token_expression.split(",")
            resolved_sub_tokens: list[str] = [
                cls.resolve_token(
                    token_expression=sub_token,
                    seed_integer=seed_integer + sub_index,
                    minimum_field_value=minimum_field_value,
                    maximum_field_value=maximum_field_value,
                    aliases=aliases,
                )
                for sub_index, sub_token in enumerate(sub_tokens)
            ]
            return ",".join(resolved_sub_tokens)

        # Handle step intervals (e.g. H/15 or H(0-30)/5)
        if "/" in token_expression:
            base_expression, step_interval = token_expression.split("/", 1)
            if "h" not in base_expression.lower():
                return token_expression

            step_int: int = int(step_interval) if step_interval.isdigit() else 1
            max_start: int = (
                minimum_field_value + step_int - 1 if base_expression.strip().upper() == "H" else maximum_field_value
            )
            resolved_base: str = cls.resolve_token(
                token_expression=base_expression,
                seed_integer=seed_integer,
                minimum_field_value=minimum_field_value,
                maximum_field_value=min(max_start, maximum_field_value),
                aliases=aliases,
            )
            return f"{resolved_base}-{maximum_field_value}/{step_interval}"

        pattern_match = cls.HASH_TOKEN_PATTERN.match(token_expression.strip())
        if not pattern_match:
            return token_expression

        range_start_string: str | None = pattern_match.group("range_start")
        range_end_string: str | None = pattern_match.group("range_end")

        lower_bound: int = minimum_field_value
        upper_bound: int = maximum_field_value

        if range_start_string and range_end_string:
            lower_bound = cls._parse_bound(range_start_string, aliases)
            upper_bound = cls._parse_bound(range_end_string, aliases)

        random_generator: Random = Random(seed_integer)
        deterministic_offset: int = random_generator.randint(lower_bound, upper_bound)

        return str(deterministic_offset)

    @classmethod
    def _get_period_start_timestamp(
        cls,
        field_type: CronFieldType,
        target_datetime: datetime,
    ) -> int:
        """Calculates Unix timestamp (seconds) at the start of the field's evaluation period.

        - SECOND: Starts at current minute (second 0)
        - MINUTE: Starts at current hour (minute 0, second 0)
        - HOUR: Starts at current day (hour 0, minute 0, second 0)
        - DAY_OF_MONTH: Starts at current month (day 1, hour 0)
        - MONTH: Starts at current year (month 1, day 1)
        - DAY_OF_WEEK: Starts at current ISO week (Monday 00:00:00)
        """
        if field_type == CronFieldType.SECOND:
            period_datetime: datetime = target_datetime.replace(second=0, microsecond=0)
        elif field_type == CronFieldType.MINUTE:
            period_datetime = target_datetime.replace(minute=0, second=0, microsecond=0)
        elif field_type == CronFieldType.HOUR:
            period_datetime = target_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        elif field_type == CronFieldType.DAY_OF_MONTH:
            period_datetime = target_datetime.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif field_type == CronFieldType.MONTH:
            period_datetime = target_datetime.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif field_type == CronFieldType.DAY_OF_WEEK:
            monday_offset: int = target_datetime.weekday()
            period_datetime = (target_datetime - timedelta(days=monday_offset)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        return int(period_datetime.timestamp())

    @staticmethod
    def _compute_stable_hash(job_name: Any, period_start_timestamp: int) -> int:
        """Computes a process-independent, cross-server 32-bit integer hash using zlib.crc32."""
        seed_bytes: bytes = f"{job_name}_{period_start_timestamp}".encode()
        return zlib.crc32(seed_bytes)

    @staticmethod
    def _parse_bound(bound_string: str, aliases: dict[str, int] | None) -> int:
        cleaned_bound: str = bound_string.lower()
        if aliases and cleaned_bound in aliases:
            return aliases[cleaned_bound]
        return int(cleaned_bound)


class CronItem:
    """Representation of a single cron expression field (second, minute, hour, day, month, day-of-week)."""

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
        """Factory method for custom sub-minute / seconds field scheduling (0-59)."""
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
        self.aliases: dict[str, int] = {name.lower(): number for name, number in (aliases or {}).items()}
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
            is_within_wrap_range = (target_value >= normalized_start) or (target_value <= normalized_end)
            return is_within_wrap_range and ((target_value - normalized_start) % self.interval == 0)

        is_within_range = range_start <= target_value <= range_end
        return is_within_range and ((target_value - range_start) % self.interval == 0)

    def _parse(self, item_expression: str) -> None:
        """Parses individual field expression, extracting range bounds and interval steps."""
        expression_to_parse: str = item_expression.strip()

        if "/" in expression_to_parse:
            expression_to_parse, interval_string = expression_to_parse.split("/", 1)
            if not interval_string.isdigit():
                raise ValueError(f"Invalid interval step '{interval_string}' in expression '{item_expression}'")
            self.interval = int(interval_string)
            if self.interval < 1:
                raise ValueError(f"Interval step must be >= 1 in expression '{item_expression}'")

        if expression_to_parse == "*":
            self.is_wildcard = self.interval == 1
            self.range_from = self.min_value
            self.range_to = self.max_value
        elif "-" in expression_to_parse:
            range_from_string, range_to_string = expression_to_parse.split("-", 1)
            self.range_from = (
                self._validate_and_convert_value(range_from_string) if range_from_string.strip() else self.min_value
            )
            self.range_to = (
                self._validate_and_convert_value(range_to_string) if range_to_string.strip() else self.max_value
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
            raise ValueError(f"Invalid range bounds: {self.range_from}-{self.range_to} in '{item_expression}'")

    def _validate_and_convert_value(self, value_string: str) -> int:
        """Converts string value or alias to integer and validates range limits."""
        cleaned_value_string: str = value_string.lower()

        if cleaned_value_string in self.aliases:
            integer_value: int = self.aliases[cleaned_value_string]
        elif cleaned_value_string.isdigit():
            integer_value = int(cleaned_value_string)
        else:
            raise ValueError(f"Invalid integer value or alias: '{value_string}'")

        if integer_value < self.min_value or (self.max_value is not None and integer_value > self.max_value):
            raise ValueError(f"Value '{integer_value}' out of allowed bounds [{self.min_value}, {self.max_value}]")

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
    """Representation of a 5-field or 6-field cron expression with POSIX compliance and Hashed Cron ('H') resolution."""

    __slots__ = (
        "second",
        "minute",
        "hour",
        "day",
        "month",
        "day_of_week",
        "raw_expression",
        "seed",
        "has_explicit_seconds_field",
    )

    def __init__(
        self,
        expression_string: str,
        seed: Any | None = None,
    ) -> None:
        self.raw_expression: str = expression_string.strip()
        self.seed: Any | None = seed

        # Expand predefined shortcuts (e.g. @daily, @hourly)
        normalized_expression: str = _PREDEFINED_CRON_SHORTCUTS.get(
            self.raw_expression.lower(),
            self.raw_expression,
        )

        # Resolve 'H' hashed tokens for initial instantiation
        if seed is not None:
            normalized_expression = HashedCronResolver.resolve_expression(
                normalized_expression,
                job_name=seed,
                target_datetime=datetime.now(),
            )

        self._build_field_items(normalized_expression)

    def is_now(self, target_datetime: datetime | None = None) -> bool:
        """Evaluates whether target_datetime matches the 5-field or 6-field cron expression."""
        if target_datetime is None:
            target_datetime = datetime.now()

        # Dynamic period-aware resolution for 'H' tokens if seed is set
        if self.seed is not None and "h" in self.raw_expression.lower():
            resolved_expression_string: str = HashedCronResolver.resolve_expression(
                self.raw_expression,
                job_name=self.seed,
                target_datetime=target_datetime,
            )
            resolved_cron_expression: CronExpression = CronExpression(
                resolved_expression_string,
                seed=None,
            )
            return resolved_cron_expression.is_now(target_datetime)

        # Python dt.weekday(): 0 = Monday, 6 = Sunday
        # Standard cron day_of_week: 0 = Sunday, 1 = Monday, ..., 6 = Saturday
        current_day_of_week: int = (target_datetime.weekday() + 1) % 7

        second_match: bool = any(item.match(target_datetime.second) for item in self.second)
        minute_match: bool = any(item.match(target_datetime.minute) for item in self.minute)
        hour_match: bool = any(item.match(target_datetime.hour) for item in self.hour)
        month_match: bool = any(item.match(target_datetime.month) for item in self.month)

        day_of_month_match: bool = any(item.match(target_datetime.day) for item in self.day)
        day_of_week_match: bool = any(item.match(current_day_of_week) for item in self.day_of_week)

        # Check POSIX rule: if both DOM and DOW are restricted (not *), use OR logic. Otherwise use AND logic.
        day_of_month_restricted: bool = not any(item.is_wildcard for item in self.day)
        day_of_week_restricted: bool = not any(item.is_wildcard for item in self.day_of_week)

        if day_of_month_restricted and day_of_week_restricted:
            date_match: bool = day_of_month_match or day_of_week_match
        else:
            date_match: bool = day_of_month_match and day_of_week_match

        return second_match and minute_match and hour_match and month_match and date_match

    def _build_field_items(self, expression_string: str) -> None:
        """Parses expression tokens into CronItem instances (standardized to 6 fields internally)."""
        expression_tokens: list[str] = expression_string.split()
        if len(expression_tokens) < 5:
            raise ValueError(
                f"Cron expression requires at least 5 fields, received {len(expression_tokens)}: '{expression_string}'"
            )

        self.has_explicit_seconds_field: bool = len(expression_tokens) >= 6

        # Standardize 5-field to 6-field internally by prepending "0" for seconds
        if len(expression_tokens) == 5:
            expression_tokens = ["0"] + expression_tokens

        (
            second_token,
            minute_token,
            hour_token,
            day_token,
            month_token,
            day_of_week_token,
        ) = expression_tokens[:6]

        self.second = [CronItem.Second(token) for token in second_token.split(",")]
        self.minute = [CronItem.Minute(token) for token in minute_token.split(",")]
        self.hour = [CronItem.Hour(token) for token in hour_token.split(",")]
        self.day = [CronItem.Day(token) for token in day_token.split(",")]
        self.month = [CronItem.Month(token) for token in month_token.split(",")]
        self.day_of_week = [CronItem.DayOfWeek(token) for token in day_of_week_token.split(",")]

    def __str__(self) -> str:
        all_fields = [
            self.second,
            self.minute,
            self.hour,
            self.day,
            self.month,
            self.day_of_week,
        ]
        active_fields = all_fields if self.has_explicit_seconds_field else all_fields[1:]
        return " ".join(",".join(str(item) for item in field_items) for field_items in active_fields)
