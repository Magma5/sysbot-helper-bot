import asyncio
import logging
import re
from dataclasses import dataclass
from enum import Enum
from time import time

from discord.ext import commands, tasks

log = logging.getLogger(__name__)


class UDPServerChecker:
    @dataclass
    class Config:
        match: str
        ip: str = ""
        port: int = 9999

        @property
        def match_pattern(self):
            return re.compile(self.match)

    class Protocol(asyncio.DatagramProtocol):
        def __init__(self, config):
            self.config = config

            self.last_active = 0
            self.match = None

        def datagram_received(self, data, addr):
            message = data.decode()

            # Check if the message matches regex
            match = self.config.match_pattern.match(message)
            if not match:
                return

            # Reset the last_active time
            self.match = match
            self.last_active = time()

    def __init__(self, config):
        self.config = config

    async def start_checking(self):
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: self.Protocol(self.config),
            local_addr=(self.config.ip, self.config.port),
        )

    def is_online(self):
        return self.protocol.last_active + 15 >= time()

    def get_variables(self):
        return {"match": self.protocol.match, "last_active": self.protocol.last_active}


class CheckerType(Enum):
    UDP_SERVER = "udp_server"


checkers_mapping = {CheckerType.UDP_SERVER: UDPServerChecker}


class CheckConnection(commands.Cog):
    class Config:
        def __init__(self, notify, checkers):
            self.notify = notify
            self.checkers = {}
            for name, checker_config in checkers.items():
                # Find checker class and initialize
                checker_type = CheckerType(checker_config.pop("type"))
                cls_config = checkers_mapping[checker_type]
                config = cls_config.Config(**checker_config)
                checker = checkers_mapping[checker_type](config)
                log.info(f"Connection checker {name} loaded with {checker_type}.")
                self.checkers[name] = checker

        @property
        def notify_list(self):
            return [self.notify]

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.status = {name: False for name in self.config.checkers.keys()}

    @commands.Cog.listener()
    async def on_ready(self):
        for checker in self.config.checkers.values():
            await checker.start_checking()
        self.check_status_loop.start()

    @tasks.loop()
    async def check_status_loop(self):
        for name, checker in self.config.checkers.items():
            online = checker.is_online()
            if self.status[name] != online:
                for channel_id in self.config.notify_list:
                    channel = self.bot.get_partial_messageable(channel_id)
                    await channel.send(f"Status for {name} has changed: {online}")
                self.status[name] = online
        await asyncio.sleep(1)

    def template_variables(self, ctx):
        return {name: checker.get_variables() for name, checker in self.config.checkers.items()}
