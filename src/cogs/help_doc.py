from pathlib import Path

from discord import Interaction, ui
from discord.ext import commands
from pydantic import BaseModel

from .utils import DiscordTextParser


class HelpDoc(commands.Cog):
    '''Interactive paginated help documentation.'''

    class Config(BaseModel):
        templates_root = 'templates/docs'

    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config

    def _load_docs(self, name):
        base = Path(self.config.templates_root)
        root = base / name
        docs: list[DiscordTextParser] = []
        if not root.resolve().is_relative_to(base.resolve()):
            raise ValueError('Invalid name')

        for fn in sorted(root.glob('*.md')):
            parser = DiscordTextParser.from_file(fn)
            if not parser.menu_id:
                continue
            docs.append(parser)
        return docs

    def _create_response(self, name, id=None):
        docs = self._load_docs(name)
        if not docs:
            return {}

        select = ui.Select(custom_id=f'help_doc:menu:{name}')
        view = ui.View(select)

        selected_doc = docs[0]

        for doc in docs:
            select.add_option(label=doc.menu_title, value=doc.menu_id)
            if doc.menu_id == id:
                selected_doc = doc

        select.placeholder = selected_doc.menu_title
        return selected_doc.make_response() | {
            'view': view
        }

    @commands.command()
    async def helpdoc(self, ctx, name: str):
        try:
            response = self._create_response(name)
        except ValueError as e:
            return await ctx.send(str(e))

        if response:
            await ctx.send(**response)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: Interaction):
        if not interaction.custom_id.startswith('help_doc:'):
            return

        args = interaction.custom_id.split(':')[1:]
        if args[0] == 'menu':
            name = args[1]
            response = self._create_response(name, interaction.data['values'][0])
            await interaction.response.edit_message(**response)
