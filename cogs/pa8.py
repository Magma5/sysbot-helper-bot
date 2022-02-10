from discord import File
from discord.commands.core import slash_command
from discord.ext import commands
from dataclasses import dataclass
from difflib import get_close_matches
from os.path import basename, splitext
from glob import glob
from itertools import chain


class Pa8(commands.Cog):
    @dataclass
    class Config:
        load_files: list[str] = ('arceusdex/*.pa8',)
        attachments_limit: int = 2
        search_results_limit: int = 5
        search_score_cutoff: float = 0.1

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    def pb8_key(self, fn):
        name = splitext(basename(fn))[0]
        return name.replace("★", "★ (Shiny)")

    def get_pkm(self, ctx, query, pkm_ext='.pa8'):
        pkm_files = set(chain(*(glob(ptn) for ptn in self.config.load_files)))

        name_mappings = {}
        for fn in pkm_files:
            name, ext = splitext(basename(fn))
            if ext == pkm_ext:
                name = name.replace("★", "★ (Shiny)")
                name_mappings[name] = fn

        if not query:
            return dict(content='You can search by Pokemon name or ID in three digits!')
        if not name_mappings:
            return dict(content=f'No {pkm_ext} files loaded!')

        query = query.lower()
        matches = []

        # exact match
        if len(query) >= 3:
            for name in name_mappings:
                if name.startswith(query):
                    matches.append(name)

        # Approximate match
        if not matches:
            matches = get_close_matches(query, name_mappings.keys(), n=self.config.search_results_limit, cutoff=self.config.search_score_cutoff)

        files = []
        content = []
        for i, match in enumerate(matches):
            name = self.pb8_key(name_mappings[match])
            if i < self.config.attachments_limit:
                content.append(f'**{name}**')
                files.append(File(name_mappings[match]))
            else:
                content.append(f'{name}')

        if files:
            return dict(content='\n'.join(content), files=files)
        return dict(content=f'{pkm_ext} file not found!')

    @commands.command(name='pa8', aliases=('pb8', 'pk8'))
    async def pkm_command(self, ctx, *, query: str = None):
        await ctx.send(**self.get_pkm(ctx, query, f'.{ctx.invoked_with}'))

    @slash_command()
    async def pa8(self, ctx, query: str):
        """Use this slash command if you want some pa8 files!"""
        await ctx.respond(**self.get_pkm(ctx, query, '.pa8'))

    @slash_command()
    async def pb8(self, ctx, query: str):
        """Use this slash command if you want some pb8 files!"""
        await ctx.respond(**self.get_pkm(ctx, query, '.pb8'))

    @slash_command()
    async def pk8(self, ctx, query: str):
        """Use this slash command if you want some pk8 files!"""
        await ctx.respond(**self.get_pkm(ctx, query, '.pk8'))
