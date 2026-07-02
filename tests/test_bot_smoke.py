import os
import tempfile
import unittest
import yaml
from pathlib import Path
from sysbot_helper.bot import Bot


class TestBotSmoke(unittest.TestCase):
    def setUp(self):
        # Set up a mock token so discord client doesn't complain about empty token
        os.environ["TOKEN"] = "mock_discord_token"

        # Create a temporary config file that enables every cog
        self.test_config = {
            "token": "mock_discord_token",
            "bot": {
                "command_prefix": "!",
            },
            "database_url": "postgresql+asyncpg://mock:mock@localhost:5432/mock",
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

        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config_test.yml"
        with open(self.config_path, "w") as f:
            yaml.dump(self.test_config, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_bot_initialization(self):
        """Verify that the bot and all of its cogs load and instantiate successfully."""
        bot = Bot(self.config_path)
        self.assertIsNotNone(bot)

        # Verify that all configured cogs are loaded
        loaded_cogs = bot.cog_list
        expected_cogs = {
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

        print(f"Successfully loaded cogs: {loaded_cogs}")
        for cog in expected_cogs:
            self.assertIn(cog, loaded_cogs, f"Expected cog '{cog}' was not loaded!")

