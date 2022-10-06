from pathlib import Path

from discord import Interaction, ui
from discord.ext import commands
from pydantic import BaseModel

from .utils import DiscordTextParser


class HelpDoc(commands.Cog):
    '''Interactive paginated help documentation.'''

    class Config(BaseModel):
        templates_root = 'templates/docs'
        options_per_menu = 25

    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config

    def _load_docs(self, name):
        base = Path(self.config.templates_root)
        root = base / name
        parser_list = []
        if not root.resolve().is_relative_to(base.resolve()):
            raise ValueError('Invalid name')

        for fn in sorted(root.glob('*.md')):
            parser = DiscordTextParser.from_file(fn)
            if not parser.menu_id:
                continue
            parser_list.append(parser)
        return parser_list

    def _create_response(self, name, id=None):
        docs = self._load_docs(name)
        if not docs:
            return {}

        menus = []
        selected_doc = docs[0]

        for i, doc in enumerate(docs):
            menu_idx = i // self.config.options_per_menu
            if menu_idx >= len(menus):
                menus.append(ui.Select(custom_id=f'help_doc:menu:{name}::{menu_idx}'))
            select = menus[menu_idx]

            match = doc.menu_id == id

            if match:
                selected_doc = doc
                select.placeholder = doc.menu_title

            select.add_option(label=doc.menu_title, value=doc.menu_id, default=match)

        return selected_doc.make_response() | {
            'view': ui.View(*menus)
        }

    async def send_docs(self, ctx, name: str):
        try:
            response = self._create_response(name)
        except ValueError as e:
            return await ctx.send(str(e))

        if response:
            await ctx.send(**response)

    @commands.command()
    async def helpdoc(self, ctx, name: str):
        await self.send_docs(ctx, name)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: Interaction):
        if not interaction.custom_id:
            return

        if not interaction.custom_id.startswith('help_doc:'):
            return

        args = interaction.custom_id.split(':')[1:]
        if args[0] == 'menu':
            name = args[1]
            response = self._create_response(name, interaction.data['values'][0])
            await interaction.response.edit_message(**response)
