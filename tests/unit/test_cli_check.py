from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from sysbot_helper import Bot, run_config_check


@pytest.mark.asyncio
async def test_validate_file_valid_config() -> None:
    """Verifies that validate_file successfully validates a valid configuration file."""
    cogs = Bot.validate_file("config.example.yml")
    assert isinstance(cogs, list)
    assert "Commands" in cogs


@pytest.mark.asyncio
async def test_run_config_check_success() -> None:
    """Verifies that run_config_check returns 0 for a valid configuration file."""
    exit_code = run_config_check([Path("config.example.yml")])
    assert exit_code == 0


@pytest.mark.asyncio
async def test_run_config_check_nonexistent_file() -> None:
    """Verifies that run_config_check returns 1 for non-existent files."""
    exit_code = run_config_check([Path("nonexistent_config_12345.yml")])
    assert exit_code == 1


@pytest.mark.asyncio
@patch("pathlib.Path.exists", return_value=True)
@patch("pathlib.Path.open", new_callable=mock_open, read_data="cogs:\n  telegram:\n    invalid_key: 123\n")
async def test_run_config_check_invalid_config(mock_file, mock_exists) -> None:
    """Verifies that run_config_check returns 1 for invalid config contents using in-memory mock."""
    exit_code = run_config_check([Path("dummy_invalid.yml")])
    assert exit_code == 1


@pytest.mark.asyncio
async def test_run_config_check_with_load_cogs_false() -> None:
    """Verifies that run_config_check works with load_cogs=False."""
    exit_code_none = run_config_check([Path("config.example.yml")], load_cogs=False)
    assert exit_code_none == 0

    cogs_none = Bot.validate_file("config.example.yml", load_cogs=False)
    assert len(cogs_none) == 0
