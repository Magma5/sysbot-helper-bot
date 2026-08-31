import copy
import os
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from sysbot_helper.bot import Bot


@pytest.fixture
def example_config_dict() -> dict:
    """Loads config.example.yml into a dictionary for test manipulation."""
    config_path = Path("config.example.yml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.integration
def test_bot_initialization_and_cog_loading() -> None:
    """Verifies that the bot and all of its configured cogs instantiate cleanly from config.example.yml."""
    os.environ["TOKEN"] = "mock_discord_token_for_testing"

    bot_instance: Bot = Bot.from_file("config.example.yml")
    assert bot_instance is not None

    loaded_cog_names: set[str] = set(bot_instance.cog_list)
    expected_cog_names: set[str] = {
        "Sysbot",
        "Commands",
        "Luck",
        "Variables",
        "Announcement",
        "Admin",
        "Time",
        "ApiMessages",
        "ApiHealth",
        "ApiWebhooks",
        "ApiSendgrid",
        "ApiS3",
        "ScheduledMessages",
    }

    for expected_cog_name in expected_cog_names:
        assert expected_cog_name in loaded_cog_names, (
            f"Expected cog '{expected_cog_name}' was not loaded into the bot instance!"
        )


def test_bot_initialization_fails_on_invalid_config(example_config_dict: dict) -> None:
    """Verifies that the bot raises a validation error when config has invalid types."""
    config = copy.deepcopy(example_config_dict)

    # Make luck.mu invalid by setting it to a string that cannot be coerced to int
    config["cogs"]["luck"]["mu"] = "invalid_string_not_an_int"

    with pytest.raises(ValidationError):
        Bot(config_dict=config)


def test_bot_initialization_without_api_config(example_config_dict: dict) -> None:
    """Verifies that the bot boots gracefully when the 'api' config block is omitted."""
    config = copy.deepcopy(example_config_dict)

    # Remove the api block
    if "api" in config:
        del config["api"]

    bot_instance = Bot(config_dict=config)
    assert bot_instance.api.enabled is False
    assert bot_instance.api.app is None

    # Ensure cogs were still loaded even without the API
    loaded_cog_names: set[str] = set(bot_instance.cog_list)
    assert "ApiHealth" in loaded_cog_names
    assert "ApiMessages" in loaded_cog_names


def test_bot_initialization_with_load_cogs_false(example_config_dict: dict) -> None:
    """Verifies that the bot loads zero cogs when load_cogs is set to False."""
    config = copy.deepcopy(example_config_dict)
    bot_instance = Bot(config_dict=config, load_cogs=False)
    assert len(bot_instance.cog_list) == 0
