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

        for index, msg_config in enumerate(self.config.messages):
            cb_name = f"message_{index}"

            async def callback(self_inst: ScheduledMessages, current_cfg: MessageConfig = msg_config) -> None:
                channel = self_inst.bot.get_channel(current_cfg.channel) or self_inst.bot.get_partial_messageable(
                    current_cfg.channel
                )
                variables = self_inst.bot.template_variables(channel)
                resolved_content = self_inst.bot.template_engine.render_string(current_cfg.template, variables).strip()
                if resolved_content:
                    await channel.send(resolved_content)

            callback.__name__ = cb_name
            task = ScheduledTask(msg_config.cron, callback=callback)
            setattr(self, f"scheduled_task_{index}", task)
