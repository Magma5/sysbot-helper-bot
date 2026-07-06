import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import yaml


@pytest.fixture
def temporary_configuration_file_path() -> Generator[Path, None, None]:
    """Generates a temporary configuration YAML file for testing bot instantiation."""
    temporary_directory: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
    configuration_file_path: Path = Path(temporary_directory.name) / "config_test.yml"

    mock_configuration: dict[str, Any] = {
        "token": "mock_discord_token_for_testing",
        "bot": {
            "command_prefix": "!",
        },
        "database_url": "sqlite+aiosqlite:///:memory:",
        "cogs": {
            "sysbot": {
                "ip": "127.0.0.1",
                "port": 6000,
            },
            "commands": {
                "text": {"ping": "pong"},
            },
            "luck": {
                "mu": 80,
                "sigma": 9,
                "max_luck": 100,
                "rating_levels": [50, 100],
            },
            "variables": {
                "test_var": "test_val",
            },
            "announcement": {},
            "admin": {
                "messages": {"lock": "locked", "unlock": "unlocked"},
            },
            "time": {
                "timezone": "Europe/Berlin",
            },
            "api_server": {},
            "autoreact": [],
            "floating_help": {
                "channels": {123: "help"},
            },
            "dm": {
                "channel": 123,
            },
            "level": {},
            "stats": {
                "channels": {123: "stats_channel"},
            },
            "telegram": {
                "bots": {"mybot": "123456789:AAGmocktokenmocktokenmocktoken"},
                "chat_link": [],
            },
            "pa8": {},
            "sysinfo": {},
            "leetcode": {
                "channels": [123],
            },
        },
        "cogs_extra": {
            "purge": {},
            "typing": {},
        },
    }

    with open(configuration_file_path, "w", encoding="utf-8") as file_stream:
        yaml.dump(mock_configuration, file_stream)

    yield configuration_file_path

    temporary_directory.cleanup()
