from typing import List
from discord.ext import commands
from dataclasses import dataclass


class Announcement(commands.Cog):
    @dataclass
    class Config:
        channels: List[int]

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
