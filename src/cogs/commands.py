from itertools import chain
from random import choice
from pathlib import Path
from discord import SlashCommand
from discord.ext.commands import Command
import logging

from discord.ext import commands
from pydantic import BaseModel

from .utils import DiscordTextParser

log = logging.getLogger(__name__)


class Commands(commands.Cog):
    class Config(BaseModel):
        text: dict[str, str] = {}
        load_files: list[str] = []
        root_dir: str = 'templates'

        @property
        def root_path(self):
            return Path(self.root_dir)

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.load_commands()

    def make_text_command(self, name, path=None, text=None):

        # Pre-process the command, read special command options
        command_options = {}

        if path is not None:
            parser = DiscordTextParser.from_file(self.config.root_path / path)
            command_options.update(parser.command_options)

        def get_response(ctx):
            # Reload the file each time the command updates
            if path is not None:
                template = ctx.env.get_template(str(path))
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

        aliases_option = command_options.get('aliases', [])

        # Register aliases too
        aliases_name = name.split(',') + aliases_option

        log.info('Register command name=%s', aliases_name)
        command_list = []

        for name in aliases_name:
            name = name.strip()
            if len(name) <= 0:
                continue
            elif name[0] in '/_':
                async def callback(self, ctx):
                    await ctx.respond(**get_response(ctx))
                cmd = SlashCommand(callback, name=name[1:], **command_options)
            else:
                async def callback(self, ctx):
                    await ctx.send(**get_response(ctx))
                cmd = Command(callback, name=name, **command_options)
            command_list.append(cmd)

        self.__cog_commands__ = tuple(chain(self.__cog_commands__, command_list))

    def load_commands(self):
        root = self.config.root_path
        files = set(chain(*(root.glob(file) for file in self.config.load_files)))

        for path in files:
            self.make_text_command(path.stem, path=path.relative_to(root))

        for name, text in self.config.text.items():
            self.make_text_command(name, text=text)
