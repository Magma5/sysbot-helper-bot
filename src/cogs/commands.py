from glob import glob
from itertools import chain
from os.path import splitext, basename, join
from random import choice

from discord.ext import commands
from pydantic import BaseModel

from .utils import DiscordTextParser


class Commands(commands.Cog):
    class Config(BaseModel):
        text: dict[str, str] = {}
        load_files: list[str] = []
        root_dir: str = 'templates'

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.load_commands()

    def make_text_command(self, name, filename=None, text=None):
        command_options = {'name': name}

        # Pre-process the command, read special command options
        if filename is not None:
            parser = DiscordTextParser.from_file(join('templates', filename))

            # Process the special key "command" that will pass as command options
            command_options.update(parser.command_options)

        @self.bot.make_command(**command_options)
        def _(ctx):
            # Reload the file each time the command updates
            if filename is not None:
                template = ctx.env.get_template(filename)
            else:
                # If text is a list, then randomly send one of them
                selected_text = text
                if isinstance(selected_text, list):
                    selected_text = choice(text)
                template = ctx.env.from_string(selected_text)

            # Render the whole file before processing
            variables = ctx.template_variables()
            rendered = template.render(variables)

            # Send either normal message or embed
            return DiscordTextParser.convert_to_response(rendered)

    def load_commands(self):
        files = set(chain(
            *(glob(file, root_dir=self.config.root_dir) for file in self.config.load_files)))

        for fn in files:
            name, _ = splitext(basename(fn))
            self.make_text_command(name, filename=fn)

        for name, text in self.config.text.items():
            self.make_text_command(name, text=text)
