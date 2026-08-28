import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.relativedelta import relativedelta
from discord.ext import commands
from pydantic import BaseModel, Field, field_validator


def _format_unit(quantity: int, singular_unit: str, plural_unit: str) -> str:
    return f"{quantity} {singular_unit if quantity == 1 else plural_unit}"


def parse_target_datetime(
    target_value: str | datetime | date | int | float,
    default_timezone_name: str = "UTC",
) -> datetime:
    default_zone = ZoneInfo(default_timezone_name)

    if isinstance(target_value, datetime):
        if target_value.tzinfo is None:
            return target_value.replace(tzinfo=default_zone)
        return target_value

    if isinstance(target_value, date):
        return datetime.combine(target_value, datetime.min.time(), tzinfo=default_zone)

    if isinstance(target_value, (int, float)):
        return datetime.fromtimestamp(target_value, tz=default_zone)

    target_string = str(target_value).strip()

    try:
        numeric_timestamp = float(target_string)
        return datetime.fromtimestamp(numeric_timestamp, tz=default_zone)
    except (ValueError, OverflowError):
        pass

    parsed_datetime = datetime.fromisoformat(target_string)
    if parsed_datetime.tzinfo is None:
        return parsed_datetime.replace(tzinfo=default_zone)

    return parsed_datetime


@dataclass(frozen=True)
class AnnualRecurrence:
    """Represents an annually recurring calendar event on a fixed month and day."""

    month: int
    day: int
    time_of_day: time | None = None

    @property
    def has_explicit_time(self) -> bool:
        return self.time_of_day is not None

    def calculate_next_occurrence(self, reference_datetime: datetime) -> datetime:
        """Calculates the upcoming occurrence of this annual event relative to reference_datetime."""
        timezone = reference_datetime.tzinfo or ZoneInfo("UTC")
        target_year = reference_datetime.year

        candidate_datetime = self._create_datetime_for_year(target_year, timezone)

        # For whole-day events without explicit time, the event remains active on the date
        # and only rolls over to next year once the reference date is strictly after the candidate date.
        if not self.has_explicit_time:
            if reference_datetime.date() > candidate_datetime.date():
                candidate_datetime = self._create_datetime_for_year(target_year + 1, timezone)
        else:
            if candidate_datetime <= reference_datetime:
                candidate_datetime = self._create_datetime_for_year(target_year + 1, timezone)

        return candidate_datetime

    def _create_datetime_for_year(self, year: int, timezone: ZoneInfo) -> datetime:
        """Constructs the datetime for the specified year, advancing leap day (Feb 29) to the next leap year."""
        if self.month == 2 and self.day == 29 and not calendar.isleap(year):
            year = self._find_next_leap_year(year)

        event_time = self.time_of_day or time(0, 0, 0)
        return datetime(
            year=year,
            month=self.month,
            day=self.day,
            hour=event_time.hour,
            minute=event_time.minute,
            second=event_time.second,
            tzinfo=timezone,
        )

    @staticmethod
    def _find_next_leap_year(start_year: int) -> int:
        current_year = start_year
        while not calendar.isleap(current_year):
            current_year += 1
        return current_year


@dataclass(frozen=True)
class CountdownSnapshot:
    target_datetime: datetime
    reference_datetime: datetime
    has_explicit_time: bool = False

    @property
    def is_today(self) -> bool:
        """True if the target datetime and reference datetime fall on the exact same calendar date."""
        return self.target_datetime.date() == self.reference_datetime.date()

    @property
    def is_past(self) -> bool:
        if not self.has_explicit_time:
            return self.target_datetime.date() < self.reference_datetime.date()
        return self.target_datetime < self.reference_datetime

    @property
    def is_future(self) -> bool:
        if not self.has_explicit_time:
            return self.target_datetime.date() > self.reference_datetime.date()
        return self.target_datetime > self.reference_datetime

    @property
    def total_difference(self) -> timedelta:
        return self.target_datetime - self.reference_datetime

    @property
    def total_days(self) -> int:
        return abs(self.total_difference).days

    @property
    def total_seconds(self) -> int:
        return int(abs(self.total_difference).total_seconds())

    @property
    def relative_delta(self) -> relativedelta:
        earlier_datetime = min(self.target_datetime, self.reference_datetime)
        later_datetime = max(self.target_datetime, self.reference_datetime)

        if (
            earlier_datetime.tzinfo is not None
            and later_datetime.tzinfo is not None
            and earlier_datetime.tzinfo != later_datetime.tzinfo
        ):
            earlier_datetime = earlier_datetime.astimezone(later_datetime.tzinfo)

        return relativedelta(later_datetime, earlier_datetime)

    @property
    def years(self) -> int:
        return self.relative_delta.years

    @property
    def months(self) -> int:
        return self.relative_delta.months

    @property
    def days(self) -> int:
        return self.relative_delta.days

    @property
    def hours(self) -> int:
        return self.relative_delta.hours

    @property
    def minutes(self) -> int:
        return self.relative_delta.minutes

    @property
    def seconds(self) -> int:
        return self.relative_delta.seconds

    @property
    def unix_timestamp(self) -> int:
        return int(self.target_datetime.timestamp())

    @property
    def discord_relative(self) -> str:
        return f"<t:{self.unix_timestamp}:R>"

    @property
    def discord_full(self) -> str:
        return f"<t:{self.unix_timestamp}:F>"

    @property
    def discord_date(self) -> str:
        return f"<t:{self.unix_timestamp}:d>"

    @property
    def discord_time(self) -> str:
        return f"<t:{self.unix_timestamp}:t>"

    @property
    def next_anniversary(self) -> "CountdownSnapshot":
        """Returns a snapshot representing the countdown to the upcoming annual anniversary."""
        annual_recurrence = AnnualRecurrence(
            month=self.target_datetime.month,
            day=self.target_datetime.day,
            time_of_day=self.target_datetime.time() if self.has_explicit_time else None,
        )
        upcoming_datetime = annual_recurrence.calculate_next_occurrence(self.reference_datetime)
        return CountdownSnapshot(
            target_datetime=upcoming_datetime,
            reference_datetime=self.reference_datetime,
            has_explicit_time=self.has_explicit_time,
        )

    @property
    def next_anniversary_ordinal(self) -> int:
        """Returns the upcoming ordinal anniversary year number (e.g., 44 for 44th anniversary)."""
        return self.next_anniversary.target_datetime.year - self.target_datetime.year

    def humanize(self) -> str:
        if not self.has_explicit_time and self.is_today:
            return "0 days"

        formatted_segments: list[str] = []

        if self.years > 0:
            formatted_segments.append(_format_unit(self.years, "year", "years"))
        if self.months > 0:
            formatted_segments.append(_format_unit(self.months, "month", "months"))
        if self.days > 0:
            formatted_segments.append(_format_unit(self.days, "day", "days"))

        if self.years == 0 and self.months == 0:
            if self.has_explicit_time:
                if self.hours > 0:
                    formatted_segments.append(_format_unit(self.hours, "hour", "hours"))
                if self.minutes > 0:
                    formatted_segments.append(_format_unit(self.minutes, "minute", "minutes"))
                if self.seconds > 0 or not formatted_segments:
                    formatted_segments.append(_format_unit(self.seconds, "second", "seconds"))
            elif not formatted_segments:
                return "0 days"

        if not formatted_segments:
            return "0 days" if not self.has_explicit_time else "0 seconds"

        return ", ".join(formatted_segments)

    def __str__(self) -> str:
        return self.humanize()


EventTargetInput = str | int | float | datetime | date
EventTargetDefinition = datetime | AnnualRecurrence


def _has_explicit_time_component(raw_value: EventTargetInput) -> bool:
    if isinstance(raw_value, datetime):
        return True
    if isinstance(raw_value, date):
        return False
    if isinstance(raw_value, (int, float)):
        return True
    raw_string = str(raw_value).strip()
    try:
        float(raw_string)
        return True
    except (ValueError, OverflowError):
        pass
    return "T" in raw_string or ":" in raw_string


def parse_event_target(
    raw_target_value: EventTargetInput,
    default_timezone_name: str = "UTC",
) -> EventTargetDefinition:
    """Parses an event target into either a fixed datetime or an AnnualRecurrence object."""
    if isinstance(raw_target_value, str):
        cleaned_string = raw_target_value.strip().removeprefix("--")
        segments = cleaned_string.split("-")
        if len(segments) == 2:
            try:
                if "T" in segments[1] or ":" in segments[1]:
                    day_part, time_part = segments[1].split("T") if "T" in segments[1] else segments[1].split(" ", 1)
                    month = int(segments[0])
                    day = int(day_part)
                    parsed_time = time.fromisoformat(time_part)
                    datetime(2024, month, day)
                    return AnnualRecurrence(month=month, day=day, time_of_day=parsed_time)

                month = int(segments[0])
                day = int(segments[1])
                datetime(2024, month, day)
                return AnnualRecurrence(month=month, day=day, time_of_day=None)
            except ValueError as error:
                raise ValueError(f"Invalid annual recurring date format: '{raw_target_value}'") from error

    return parse_target_datetime(raw_target_value, default_timezone_name)


class Countdown(commands.Cog):
    class Config(BaseModel):
        default_timezone: str = "UTC"
        events: dict[str, EventTargetInput] = Field(default_factory=dict)

        @field_validator("default_timezone")
        @classmethod
        def validate_default_timezone(cls, timezone_name: str) -> str:
            try:
                ZoneInfo(timezone_name)
            except (KeyError, ValueError, ZoneInfoNotFoundError) as error:
                raise ValueError(f"Invalid timezone configuration: '{timezone_name}'") from error
            return timezone_name

        @field_validator("events")
        @classmethod
        def validate_events(cls, events_map: dict[str, EventTargetInput]) -> dict[str, EventTargetInput]:
            for event_name, raw_target in events_map.items():
                try:
                    parse_event_target(raw_target)
                except Exception as parse_error:
                    raise ValueError(f"Invalid date/time for event '{event_name}': {raw_target!r}") from parse_error
            return events_map

    def __init__(self, bot: commands.Bot, config: Config) -> None:
        self.bot = bot
        self.config = config
        self._parsed_events: dict[str, tuple[EventTargetDefinition, bool]] = {
            event_name: (
                parse_event_target(target_value, self.config.default_timezone),
                _has_explicit_time_component(target_value),
            )
            for event_name, target_value in self.config.events.items()
        }

    def template_variables(self, ctx: Any) -> dict[str, Any]:
        guild = getattr(ctx, "guild", None)
        guild_config = self.bot.guild_config(guild) if guild else {}
        server_timezone_name: str = guild_config.get(
            "timezone",
            self.config.default_timezone,
        )
        server_zone = ZoneInfo(server_timezone_name)

        return {
            event_name: lambda target_tuple=target_tuple: self._resolve_snapshot(
                target_tuple[0],
                target_tuple[1],
                server_zone,
            )
            for event_name, target_tuple in self._parsed_events.items()
        }

    def _resolve_snapshot(
        self,
        target_definition: EventTargetDefinition,
        has_explicit_time: bool,
        server_zone: ZoneInfo,
    ) -> CountdownSnapshot:
        current_time = datetime.now(server_zone)
        if isinstance(target_definition, AnnualRecurrence):
            target_datetime = target_definition.calculate_next_occurrence(current_time)
            has_explicit = target_definition.has_explicit_time
        else:
            target_datetime = target_definition
            has_explicit = has_explicit_time

        return CountdownSnapshot(
            target_datetime=target_datetime,
            reference_datetime=current_time,
            has_explicit_time=has_explicit,
        )
