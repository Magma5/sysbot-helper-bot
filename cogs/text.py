from typing import Dict, List
from discord.ext import commands
from dataclasses import dataclass, field
from glob import glob
from itertools import chain
from os.path import splitext, basename


class Text(commands.Cog):
    @dataclass
    class Config:
        load_files: List[str]
        commands: Dict = field(default_factory=dict)

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self._load_commands()

    def _load_commands(self):
        files = set(chain(*(glob(x) for x in self.config.load_files)))
        commands = []

        # Load text commands from file and from variable
        for fn in files:
            with open(fn) as f:
                text = f.read().strip()
            name, _ = splitext(basename(fn))
            commands.append((name, text))
        commands.extend((k, v) for k, v in self.config.commands.items())

        # Register the commands
        def make_text_command(name, text):
            @self.bot.helper.make_command(name=name)
            def text_command(ctx):
                variables = self.bot.helper.template_variables(ctx)
                return {'content': text.format(**variables)}
        for name, text in commands:
            make_text_command(name, text)
