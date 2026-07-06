import unittest
from unittest.mock import MagicMock

from sysbot_helper import Bot
from sysbot_helper.cogs.scheduled_messages import (
    MessageConfig,
    ScheduledMessages,
    ScheduledMessagesConfig,
)
from sysbot_helper.schedule import ScheduledTask


class TestScheduledMessages(unittest.TestCase):
    def test_scheduled_messages_initialization(self) -> None:
        """Verifies that ScheduledMessages cog dynamically creates ScheduledTask attributes from config."""
        bot_mock = MagicMock(spec=Bot)

        config = ScheduledMessagesConfig(
            messages=[
                MessageConfig(
                    channel=1005693058119122984,
                    cron="H/15 * * * * *",
                    template="Server time is: {{ now.strftime('%T') }}",
                )
            ]
        )

        cog = ScheduledMessages(bot_mock, config)

        # Check that dynamic attribute exists and is correct type
        self.assertTrue(hasattr(cog, "scheduled_task_0"))
        task = cog.scheduled_task_0
        self.assertIsInstance(task, ScheduledTask)
        self.assertEqual(task.raw_schedules[0], "H/15 * * * * *")
