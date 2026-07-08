import os
from pathlib import Path

import pytest
from sysbot_helper.bot import Bot


@pytest.mark.integration
def test_bot_initialization_and_cog_loading(
    temporary_configuration_file_path: Path,
) -> None:
    """Verifies that the bot and all of its configured cogs instantiate cleanly."""
    os.environ["TOKEN"] = "mock_discord_token_for_testing"

    bot_instance: Bot = Bot(temporary_configuration_file_path)

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
        "ApiServer",
        "Autoreact",
        "FloatingHelp",
        "Dm",
        "Level",
        "Stats",
        "Telegram",
        "Pa8",
        "Sysinfo",
        "Leetcode",
        "Purge",
        "Typing",
    }

    for expected_cog_name in expected_cog_names:
        assert (
            expected_cog_name in loaded_cog_names
        ), f"Expected cog '{expected_cog_name}' was not loaded into the bot instance!"


def test_bot_initialization_fails_on_invalid_config(
    temporary_configuration_file_path: Path,
) -> None:
    """Verifies that the bot raises a validation error when config has invalid types."""
    import yaml
    from pydantic import ValidationError

    # Read the valid config, modify it to be invalid, and save it
    with open(temporary_configuration_file_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Make luck.mu invalid by setting it to a string that cannot be coerced to int
    config["cogs"]["luck"]["mu"] = "invalid_string_not_an_int"

    # Write it back to a temp file
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".yml", mode="w", delete=False) as temp_f:
        yaml.dump(config, temp_f)
        temp_path = Path(temp_f.name)

    try:
        with pytest.raises(ValidationError):
            Bot(temp_path)
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
