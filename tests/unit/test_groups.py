import tempfile
import unittest
from pathlib import Path
from typing import Any

from sysbot_helper.groups import Groups


class TestGroups(unittest.TestCase):
    def test_group_member_resolution_with_nested_structures(self) -> None:
        """Verifies BFS expansion of members across deeply nested dictionaries and list values."""
        temporary_directory: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        save_file_path: Path = Path(temporary_directory.name) / "sysbot_channels.json"
        save_file_path.write_text("{}", encoding="utf-8")

        group_configuration: dict[str, Any] = {
            "channel_alpha": 100,
            "channel_group_beta": [
                200,
                [300, [301, 302, {"sub_group": 800}]],
                {"sub_channel": 400},
            ],
            "empty_group": {},
            "target_channels": 999999,
        }

        groups: Groups = Groups(group_configuration, save_file=str(save_file_path))
        beta_members: set[int] = groups.get_members("channel_group_beta")

        self.assertIn(200, beta_members)
        self.assertIn(300, beta_members)
        self.assertIn(301, beta_members)
        self.assertIn(302, beta_members)
        self.assertIn(400, beta_members)
        self.assertIn(800, beta_members)
        self.assertNotIn(100, beta_members)

        temporary_directory.cleanup()

    def test_group_persistence_and_member_addition(self) -> None:
        """Verifies saved group membership updates and JSON file persistence."""
        temporary_directory: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        save_file_path: Path = Path(temporary_directory.name) / "sysbot_channels.json"
        save_file_path.write_text("{}", encoding="utf-8")

        groups: Groups = Groups({}, save_file=str(save_file_path))
        groups.add_member_save("custom_saved_group", 1111, 2222)

        saved_members: set[int] = groups.get_members("custom_saved_group")
        self.assertIn(1111, saved_members)
        self.assertIn(2222, saved_members)

        # Reload group from saved JSON file to ensure immutability/persistence
        reloaded_groups: Groups = Groups({}, save_file=str(save_file_path))
        reloaded_members: set[int] = reloaded_groups.get_members("custom_saved_group")
        self.assertIn(1111, reloaded_members)
        self.assertIn(2222, reloaded_members)

        temporary_directory.cleanup()
