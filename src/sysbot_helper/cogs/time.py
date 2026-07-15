from collections.abc import Iterator, Mapping
from datetime import datetime
from functools import cache
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from discord.ext import commands
from pydantic import BaseModel, field_validator


@cache
def build_timezone_lookup_map() -> dict[str, ZoneInfo]:
    """Pre-computes an O(1) lookup dictionary mapping normalized timezone identifiers
    and city shortcuts to ZoneInfo objects.
    """
    lookup_map: dict[str, ZoneInfo] = {}

    for timezone_name in available_timezones():
        try:
            zone_info = ZoneInfo(timezone_name)
        except Exception:
            continue

        # 1. Exact IANA string (e.g. "Asia/Tokyo", "America/New_York")
        lookup_map[timezone_name] = zone_info
        lookup_map[timezone_name.lower()] = zone_info

        # 2. Underscore replaced path (e.g. "Asia_Tokyo", "America_Indiana_Indianapolis")
        underscore_variant = timezone_name.replace("/", "_")
        lookup_map[underscore_variant] = zone_info
        lookup_map[underscore_variant.lower()] = zone_info

        # 3. Exact final segment city name (e.g. "Tokyo" -> "Asia/Tokyo", "New_York" -> "America/New_York")
        city_segment = timezone_name.split("/")[-1]
        city_lower = city_segment.lower()
        if city_lower not in lookup_map:
            lookup_map[city_lower] = zone_info

        city_no_underscore = city_segment.replace("_", "").lower()
        if city_no_underscore not in lookup_map:
            lookup_map[city_no_underscore] = zone_info

    return lookup_map


def resolve_timezone(key: str, server_timezone: str = "UTC") -> ZoneInfo:
    """Resolves a timezone string, alias, or city shortcut in O(1) time."""
    if key == "now":
        return ZoneInfo(server_timezone)
    if key == "utcnow":
        return ZoneInfo("UTC")

    # Direct ZoneInfo lookup
    try:
        return ZoneInfo(key)
    except (KeyError, ValueError, ZoneInfoNotFoundError):
        pass

    # O(1) normalized lookup map search
    normalized_key = key.lower().strip()
    lookup_map = build_timezone_lookup_map()

    if normalized_key in lookup_map:
        return lookup_map[normalized_key]

    raise KeyError(f"Invalid timezone identifier: '{key}'")


class TimeContext(Mapping[str, datetime]):
    """Dynamic context mapping for template variable time and timezone evaluation."""

    def __init__(self, server_timezone: str) -> None:
        self.server_timezone: str = server_timezone

    def __getitem__(self, key: str) -> datetime:
        zone_info: ZoneInfo = resolve_timezone(key, self.server_timezone)
        return datetime.now(zone_info)

    def __iter__(self) -> Iterator[str]:
        yield from ("now", "utcnow")

    def __len__(self) -> int:
        return 2

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        try:
            resolve_timezone(key, self.server_timezone)
            return True
        except KeyError:
            return False


class Time(commands.Cog):
    class Config(BaseModel):
        timezone: str = "UTC"

        @field_validator("timezone")
        @classmethod
        def validate_timezone(cls, value: str) -> str:
            try:
                ZoneInfo(value)
            except (KeyError, ValueError, ZoneInfoNotFoundError) as err:
                raise ValueError(f"Invalid timezone configuration: '{value}'") from err
            return value

    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config

    def server_now(self, ctx: Any) -> datetime:
        target_timezone_name: str = self.bot.guild_config(ctx.guild).get("timezone", self.config.timezone)
        return datetime.now(ZoneInfo(target_timezone_name))

    def now(self) -> datetime:
        return datetime.now(ZoneInfo(self.config.timezone))

    def template_variables(self, ctx: Any) -> TimeContext:
        server_timezone: str = self.bot.guild_config(ctx.guild).get("timezone", self.config.timezone)
        return TimeContext(server_timezone=server_timezone)
