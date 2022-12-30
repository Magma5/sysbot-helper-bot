import asyncio
import logging

from discord.ext import commands
from pydantic import BaseModel
from sysbot_helper import Bot, scheduled

log = logging.getLogger(__name__)


class Stats(commands.Cog):
    class Config(BaseModel):
        channels: dict[int, str]

    def __init__(self, bot: Bot, config: Config):
        self.bot = bot
        self.config = config

    @scheduled("*/15 * * * *")
    async def run_update(self):
        for channel_id, channel_template in self.config.channels.items():
            channel = self.bot.get_channel(channel_id)
            guild = channel.guild

            variables = self.bot.template_variables(channel)

            # Render template
            template = self.bot.template_env.from_string(channel_template)
            text = template.render(variables)

            if channel.name == text:
                continue

            log.info("%s %s -> %s", guild.name, channel.name, text)

            try:
                await asyncio.wait_for(channel.edit(name=text), timeout=3)
            except asyncio.exceptions.TimeoutError as e:
                log.error("%s timeout: %s %s", guild.name, e, channel.name)
