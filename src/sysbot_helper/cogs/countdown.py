from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
class CountdownSnapshot:
    target_datetime: datetime
    reference_datetime: datetime

    @property
    def is_past(self) -> bool:
        return self.target_datetime < self.reference_datetime

    @property
    def is_future(self) -> bool:
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

    def humanize(self) -> str:
        formatted_segments: list[str] = []

        if self.years > 0:
            formatted_segments.append(_format_unit(self.years, "year", "years"))
        if self.months > 0:
            formatted_segments.append(_format_unit(self.months, "month", "months"))
        if self.days > 0:
            formatted_segments.append(_format_unit(self.days, "day", "days"))

        if self.years == 0 and self.months == 0:
            if self.hours > 0:
                formatted_segments.append(_format_unit(self.hours, "hour", "hours"))
            if self.minutes > 0:
                formatted_segments.append(_format_unit(self.minutes, "minute", "minutes"))
            if self.seconds > 0 or not formatted_segments:
                formatted_segments.append(_format_unit(self.seconds, "second", "seconds"))

        if not formatted_segments:
            return "0 seconds"

        return ", ".join(formatted_segments)

    def __str__(self) -> str:
        return self.humanize()


EventTargetInput = str | int | float | datetime | date


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
                    parse_target_datetime(raw_target)
                except Exception as parse_error:
                    raise ValueError(f"Invalid date/time for event '{event_name}': {raw_target!r}") from parse_error
            return events_map

    def __init__(self, bot: commands.Bot, config: Config) -> None:
        self.bot = bot
        self.config = config
        self._parsed_events: dict[str, datetime] = {
            event_name: parse_target_datetime(target_value, self.config.default_timezone)
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
            event_name: lambda target_dt=target_dt: CountdownSnapshot(
                target_datetime=target_dt,
                reference_datetime=datetime.now(server_zone),
            )
            for event_name, target_dt in self._parsed_events.items()
        }
