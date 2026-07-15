import calendar
import re
import zlib
from collections.abc import Hashable
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from random import Random


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
        job_name: Hashable | None = None,
        target_datetime: datetime | None = None,
    ) -> str:
        """Resolves all 'H' tokens in a 5-field or 6-field cron expression into numeric cron values."""
        normalized_expression: str = _PREDEFINED_CRON_SHORTCUTS.get(
            expression_string.strip().lower(),
            expression_string.strip(),
        )

        tokens: list[str] = normalized_expression.split()
        if len(tokens) < 5 or job_name is None:
            return normalized_expression

        is_five_field: bool = len(tokens) == 5
        if is_five_field:
            tokens = ["0"] + tokens

        if target_datetime is None:
            target_datetime = datetime.now(UTC)

        resolved_tokens: list[str] = []
        for index, (field_type, min_val, max_val, aliases) in enumerate(cls.FIELD_SPECIFICATIONS):
            token: str = tokens[index]
            period_start_timestamp: int = cls._get_period_start_timestamp(
                field_type=field_type,
                target_datetime=target_datetime,
            )

            combined_seed_integer: int = cls._compute_stable_hash(
                job_name=job_name,
                field_type=field_type,
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
        """Resolves a single token like 'H', 'H(10-30)', or 'H/15' into standard numeric cron syntax."""
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

        if "/" in token_expression:
            base_expression, step_interval = token_expression.split("/", 1)
            if "h" not in base_expression.lower():
                return token_expression

            step_int: int = int(step_interval) if step_interval.isdigit() else 1

            pattern_match = cls.HASH_TOKEN_PATTERN.match(base_expression.strip())
            range_end_str = pattern_match.group("range_end") if pattern_match else None
            range_start_str = pattern_match.group("range_start") if pattern_match else None

            upper_limit = maximum_field_value
            lower_limit = minimum_field_value
            if range_end_str:
                upper_limit = cls._parse_bound(range_end_str, aliases)
            if range_start_str:
                lower_limit = cls._parse_bound(range_start_str, aliases)

            if lower_limit <= upper_limit:
                max_start: int = min(lower_limit + step_int - 1, upper_limit)
                resolved_base: str = cls.resolve_token(
                    token_expression=base_expression,
                    seed_integer=seed_integer,
                    minimum_field_value=lower_limit,
                    maximum_field_value=max_start,
                    aliases=aliases,
                )
                return f"{resolved_base}-{upper_limit}/{step_interval}"

            # Cyclic wrap-around range (e.g. H(22-5)/5)
            span = (maximum_field_value - lower_limit + 1) + (upper_limit - minimum_field_value + 1)
            allowed_start_span = min(step_int, span)

            random_generator = Random(seed_integer)
            start_offset_within_span = random_generator.randint(0, allowed_start_span - 1)
            start_offset = lower_limit + start_offset_within_span
            if start_offset > maximum_field_value:
                start_offset = minimum_field_value + (start_offset - maximum_field_value - 1)

            if start_offset >= lower_limit:
                leg1 = f"{start_offset}-{maximum_field_value}/{step_interval}"
                next_start = start_offset + step_int
                second_leg_start = minimum_field_value + (next_start - maximum_field_value - 1)
                if second_leg_start <= upper_limit:
                    leg2 = f"{second_leg_start}-{upper_limit}/{step_interval}"
                    return f"{leg1},{leg2}"
                return leg1
            else:
                return f"{start_offset}-{upper_limit}/{step_interval}"

        pattern_match = cls.HASH_TOKEN_PATTERN.match(token_expression.strip())
        if not pattern_match:
            return token_expression

        range_start_string: str | None = pattern_match.group("range_start")
        range_end_string: str | None = pattern_match.group("range_end")

        lower_bound: int = minimum_field_value
        upper_bound: int = maximum_field_value

        if range_start_string and range_end_string:
            parsed_start: int = cls._parse_bound(range_start_string, aliases)
            parsed_end: int = cls._parse_bound(range_end_string, aliases)
            lower_bound = max(lower_bound, parsed_start)
            upper_bound = min(upper_bound, parsed_end)

        random_generator: Random = Random(seed_integer)
        if lower_bound <= upper_bound:
            deterministic_offset: int = random_generator.randint(lower_bound, upper_bound)
        else:
            span = (maximum_field_value - lower_bound + 1) + (upper_bound - minimum_field_value + 1)
            offset_within_span = random_generator.randint(0, span - 1)
            deterministic_offset = lower_bound + offset_within_span
            if deterministic_offset > maximum_field_value:
                deterministic_offset = minimum_field_value + (deterministic_offset - maximum_field_value - 1)

        return str(deterministic_offset)

    @classmethod
    def _get_period_start_timestamp(
        cls,
        field_type: CronFieldType,
        target_datetime: datetime,
    ) -> int:
        """Calculates Unix timestamp (seconds) at the start of the field's evaluation period."""
        if target_datetime.tzinfo is None:
            target_datetime = target_datetime.replace(tzinfo=UTC)

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
    def _compute_stable_hash(job_name: Hashable, field_type: CronFieldType, period_start_timestamp: int) -> int:
        """Computes a process-independent, cross-server 32-bit integer hash using zlib.crc32."""
        seed_bytes: bytes = f"{job_name}_{field_type.name}_{period_start_timestamp}".encode()
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
            if target_value == 7:
                target_value = 0

            if range_start == 0 and range_end >= 6:
                return (target_value - range_start) % self.interval == 0

            normalized_start: int = 0 if range_start == 7 else range_start
            normalized_end: int = 0 if range_end == 7 else range_end

            if normalized_start <= normalized_end:
                return (
                    normalized_start <= target_value <= normalized_end
                    and (target_value - normalized_start) % self.interval == 0
                )

            is_within_wrap_range = (target_value >= normalized_start) or (target_value <= normalized_end)
            if not is_within_wrap_range:
                return False
            step_offset = (target_value - normalized_start) % 7
            return step_offset % self.interval == 0

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
            if self.range_from <= self.min_value and self.range_to >= self.max_value:
                self.is_wildcard = self.interval == 1
            elif self.is_day_of_week and (self.range_to - self.range_from >= 6):
                self.is_wildcard = self.interval == 1
        else:
            start_value: int = self._validate_and_convert_value(expression_to_parse)
            self.range_from = start_value
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
        seed: Hashable | None = None,
    ) -> None:
        self.raw_expression: str = expression_string.strip()
        self.seed: Hashable | None = seed

        normalized_expression: str = _PREDEFINED_CRON_SHORTCUTS.get(
            self.raw_expression.lower(),
            self.raw_expression,
        )

        if seed is not None:
            normalized_expression = HashedCronResolver.resolve_expression(
                normalized_expression,
                job_name=seed,
                target_datetime=datetime.now(UTC),
            )

        self._build_field_items(normalized_expression)

    def is_now(self, target_datetime: datetime | None = None) -> bool:
        """Evaluates whether target_datetime matches the 5-field or 6-field cron expression."""
        if target_datetime is None:
            target_datetime = datetime.now(UTC)

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

        current_day_of_week: int = (target_datetime.weekday() + 1) % 7

        second_match: bool = any(item.match(target_datetime.second) for item in self.second)
        minute_match: bool = any(item.match(target_datetime.minute) for item in self.minute)
        hour_match: bool = any(item.match(target_datetime.hour) for item in self.hour)
        month_match: bool = any(item.match(target_datetime.month) for item in self.month)

        day_of_month_match: bool = any(item.match(target_datetime.day) for item in self.day)
        day_of_week_match: bool = any(item.match(current_day_of_week) for item in self.day_of_week)

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
