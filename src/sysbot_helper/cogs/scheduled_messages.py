from discord.ext import commands
from pydantic import BaseModel

from sysbot_helper import Bot
from sysbot_helper.schedule import ScheduledTask


class MessageConfig(BaseModel):
    channel: int
    cron: str
    template: str


class ScheduledMessagesConfig(BaseModel):
    messages: list[MessageConfig]


class ScheduledMessages(commands.Cog):
    """Cog for running configuration-driven scheduled messages using 5-field/6-field cron."""

    def __init__(self, bot: Bot, config: ScheduledMessagesConfig):
        self.bot = bot
        self.config = config

        def make_callback(msg_cfg: MessageConfig):
            async def callback(self_inst: ScheduledMessages) -> None:
                channel = self_inst.bot.get_partial_messageable(msg_cfg.channel)
                variables = self_inst.bot.template_variables(channel)
                resolved_content = self_inst.bot.template_engine.render_string(msg_cfg.template, variables).strip()
                if resolved_content:
                    await channel.send(resolved_content)

            return callback

        for index, msg_config in enumerate(self.config.messages):
            task = ScheduledTask(msg_config.cron, callback=make_callback(msg_config))
            setattr(self, f"scheduled_task_{index}", task)
