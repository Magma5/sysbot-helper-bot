from discord import File
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

    @commands.command(aliases=('pb8', 'pk8', 'pkm'))
    async def pa8(self, ctx, *, text: str = None):
        pa8_files = set(*chain(glob(ptn) for ptn in self.config.load_files))
        name_mappings = {self.pb8_key(fn).lower(): fn for fn in pa8_files}

        if not text:
            return await ctx.send('Please request a pokemon name!')

        text = text.lower()

        # exact match
        for name in name_mappings:
            if name.startswith(text):
                return await ctx.send('Here is the .pb8 file:', file=File(name_mappings[name]))

        # Approximate match
        matches = get_close_matches(text, name_mappings.keys(), n=self.config.search_results_limit, cutoff=self.config.search_score_cutoff)
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
            await ctx.send(content='\n'.join(content), files=files)
        else:
            await ctx.send('.pa8 file not found!')
