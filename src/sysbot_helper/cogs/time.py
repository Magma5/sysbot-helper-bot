from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from discord.ext import commands
from pydantic import BaseModel, field_validator


class TimeContext(dict[str, datetime]):
    """Dynamic context mapping for template variable time and timezone evaluation."""

    def __init__(self, server_timezone: str) -> None:
        super().__init__()
        self.server_timezone: str = server_timezone

    def _resolve_zone(self, key: str) -> ZoneInfo:
        if key == "now":
            return ZoneInfo(self.server_timezone)

        if key == "utcnow":
            return ZoneInfo("UTC")

        # 1. Direct ZoneInfo lookup (e.g. "Asia/Tokyo" or "UTC")
        try:
            return ZoneInfo(key)
        except (KeyError, ValueError, ZoneInfoNotFoundError):
            pass

        # 2. Iterative underscore replacement for multi-part timezones (e.g. "America_Indiana_Indianapolis")
        formatted_key: str = key
        while "_" in formatted_key:
            formatted_key = formatted_key.replace("_", "/", 1)
            try:
                return ZoneInfo(formatted_key)
            except (KeyError, ValueError, ZoneInfoNotFoundError):
                continue

        # 3. Case-insensitive city shortcut or suffix lookup (e.g. "New_York", "tokyo", "berlin")
        normalized_target: str = key.lower().replace("_", "").replace("/", "")
        for timezone_name in available_timezones():
            normalized_name: str = timezone_name.lower().replace("_", "").replace("/", "")
            if normalized_name == normalized_target or normalized_name.endswith(normalized_target):
                try:
                    return ZoneInfo(timezone_name)
                except (KeyError, ValueError, ZoneInfoNotFoundError):
                    continue

        raise KeyError(f"Invalid timezone identifier: '{key}'")

    def __getitem__(self, key: str) -> datetime:
        zone_info: ZoneInfo = self._resolve_zone(key)
        return datetime.now(zone_info)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        try:
            self._resolve_zone(key)
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
