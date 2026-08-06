import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from sysbot_helper import Bot, run_config_check


class TestCLICheck(unittest.TestCase):
    def test_validate_file_valid_config(self) -> None:
        """Verifies that validate_file successfully validates a valid configuration file."""
        cogs = Bot.validate_file("config.example.yml")
        self.assertIsInstance(cogs, list)
        self.assertIn("Commands", cogs)

    def test_run_config_check_success(self) -> None:
        """Verifies that run_config_check returns 0 for a valid configuration file."""
        exit_code = run_config_check([Path("config.example.yml")])
        self.assertEqual(exit_code, 0)

    def test_run_config_check_nonexistent_file(self) -> None:
        """Verifies that run_config_check returns 1 for non-existent files."""
        exit_code = run_config_check([Path("nonexistent_config_12345.yml")])
        self.assertEqual(exit_code, 1)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.open", new_callable=mock_open, read_data="cogs:\n  telegram:\n    invalid_key: 123\n")
    def test_run_config_check_invalid_config(self, mock_file, mock_exists) -> None:
        """Verifies that run_config_check returns 1 for invalid config contents using in-memory mock."""
        exit_code = run_config_check([Path("dummy_invalid.yml")])
        self.assertEqual(exit_code, 1)
