from typing import List
import discord
from discord.ext import commands
from dataclasses import dataclass
from glob import glob
from itertools import chain
from os.path import splitext, basename
import yaml


class Embeds(commands.Cog):
    @classmethod
    def parse_fields(cls, fields_text, inline=True):
        fields = []
        field_sections = fields_text.split('\n\n')
        for section in field_sections:
            lines = section.strip().split('\n')
            if not lines:
                continue
            fields.append({
                'name': lines[0],
                'value': '\n'.join(lines[1:]),
                'inline': inline
            })
        return fields

    @classmethod
    def parse_embed(cls, embed_text):
        # Find headers first
        headers = {}
        headers_split = embed_text.split('---\n', 1)
        if len(headers_split) == 1:
            content_section = headers_split[0]
        else:
            header_section, content_section = headers_split[1].split('---', 1)
            headers = yaml.safe_load(header_section)

        # Find description/fields split
        fields = []
        content_split = content_section.split('\n\n\n', 1)
        if len(content_split) == 1:
            description_section = content_split[0]
        else:
            description_section, fields_section = content_split
            fields = cls.parse_fields(fields_section)
        return cls.make_embed(headers, description_section.strip(), fields)

    @classmethod
    def make_embed(cls, headers, description, fields):
        params = {k: v for k, v in headers.items() if type(v) not in (dict, list)}
        embed = discord.Embed(description=description, **params)

        for method_name in headers.keys() - params.keys():
            method_params = headers[method_name]

            # Load the embed method given method name
            if not hasattr(embed, method_name):
                continue
            method = getattr(embed, method_name)

            # Determine calling method multiple times
            if type(method_params) is dict:
                method_params = [method_params]

            # Apply the given method
            for item in method_params:
                method(**item)

        for field in fields:
            embed.add_field(**field)

        return embed

    @classmethod
    def load_embed(cls, fn):
        with open(fn) as f:
            embed_data = f.read()

        return cls.parse_embed(embed_data)

    @dataclass
    class Config:
        load_files: List[str]

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self._load_commands()

    def _load_commands(self):
        files = set(chain(*(glob(x) for x in self.config.load_files)))

        def make_embed_command(name, embed):
            @self.bot.helper.make_command(name=name)
            def embed_command(ctx):
                return {'embed': embed}

        for fn in files:
            embed = self.load_embed(fn)
            name, _ = splitext(basename(fn))
            make_embed_command(name, embed)
