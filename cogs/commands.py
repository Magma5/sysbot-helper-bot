from typing import List, Dict
from discord.ext import commands
from dataclasses import dataclass, field
from glob import glob
from itertools import chain
from os.path import splitext, basename
from random import choice


class Commands(commands.Cog):
    @dataclass
    class Config:
        text: Dict = field(default_factory=dict)
        load_files: List[str] = field(default_factory=list)

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.load_commands()

    def make_command_from_file(self, name, fn):
        @self.bot.make_command(name=name)
        def _(ctx):
            template = ctx.env.get_template(fn)
            parser = ctx.DiscordTextParser(
                template.render(
                    ctx.template_variables()))
            response = parser.make_response(color=ctx.author.color)
            return response

    def make_command_from_text(self, name, text):
        @self.bot.make_command(name=name)
        def _(ctx):
            selected_text = text
            # If text is a list, then randomly send one of them
            if isinstance(text, list):
                selected_text = choice(text)
            template = ctx.env.from_string(selected_text)
            parser = ctx.DiscordTextParser(
                template.render(
                    ctx.template_variables()))
            response = parser.make_response(color=ctx.author.color)
            return response

    def load_commands(self):
        files = set(chain(
            *(glob(file, root_dir='templates') for file in self.config.load_files)))

        for fn in files:
            name, _ = splitext(basename(fn))
            self.make_command_from_file(name, fn)

        for name, text in self.config.text.items():
            self.make_command_from_text(name, text)
