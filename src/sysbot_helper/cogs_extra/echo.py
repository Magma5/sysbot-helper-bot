import random
from uuid import uuid4

from discord import ButtonStyle, Interaction, Member, SelectOption, slash_command, ui
from discord.ext import commands
from discord.utils import snowflake_time


class MyView(ui.View):
    @ui.select(  # the decorator that lets you specify the properties of the select menu
        placeholder="Choose a Flavor!",  # the placeholder text that will be displayed if nothing is selected
        min_values=1,  # the minimum number of values that must be selected by the users
        max_values=1,  # the maximum number of values that can be selected by the users
        options=[  # the list of options from which users can choose, a required field
            SelectOption(label="Vanilla", description="Pick this if you like vanilla!"),
            SelectOption(label="Chocolate", description="Pick this if you like chocolate!"),
            SelectOption(label="Strawberry", description="Pick this if you like strawberry!"),
        ],
    )
    async def select_callback(self, select, interaction):  # the function called when the user is done selecting options
        await interaction.response.send_message(f"Awesome! I like {select.values[0]} too!")


class Counter(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="0", style=ButtonStyle.red, row=1, custom_id="counter1")
    async def a(self, button: ui.Button, interaction: Interaction):
        # if await interaction.client.is_owner(interaction.user):
        number = int(button.label) if button.label else 0
        button.label = str(number + 1)
        await interaction.response.edit_message(view=self)
        # else:
        #     await interaction.response.send_message('You are not the owner!')


class Echo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def echo(self, ctx):
        await ctx.send("```\n" + ctx.message.content + "```")

    @commands.command()
    async def timeformat(self, ctx, *, format):
        now = self.bot.get_cog("Time").server_now(ctx)
        await ctx.send(now.strftime(format))

    @commands.command()
    async def id(self, ctx, id: int):
        resp = []
        creation = snowflake_time(id)
        resp.append(f"ID: **{id}**")
        resp.append(f"Creation time: {creation.isoformat()}")
        await ctx.send("\n".join(resp))

    @commands.command()
    async def avatar(self, ctx, user: Member | None):
        if not user:
            user = ctx.author
        async for a in ctx.channel.history():
            print(a)
        await ctx.send(user.avatar.url)

    @slash_command()
    async def button(self, ctx):
        view = ui.View()
        for _ in range(25):
            btn = ui.Button(
                label="0",
                style=ButtonStyle.success,
                custom_id="Mewtwo counter " + str(uuid4()),
            )
            view.add_item(btn)

        await ctx.respond("This is a button!", view=view)

    @slash_command()
    async def button2(self, ctx):
        counter = Counter()
        await ctx.respond("This is a counter!", view=counter)
        # view = ui.View()
        # btn = ui.Button(label="0",
        #                 style=ButtonStyle.success,
        #                 custom_id="btn reply test " + str(uuid4()))
        # view.add_item(btn)

        # await ctx.respond("this is a single button!", view=view)

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(Counter())

    @commands.Cog.listener()
    async def on_interaction(self, interaction: Interaction):
        if not interaction.custom_id:
            return

        if interaction.custom_id.startswith("Mewtwo counter"):
            view = ui.View.from_message(interaction.message)
            counter = None

            for component in view.children:
                if isinstance(component, ui.Button) and component.custom_id == interaction.custom_id:
                    component.style = ButtonStyle(random.randint(1, 4))
                    component.label = str(int(component.label) + 1)
                    counter = component.label

            await interaction.response.edit_message(view=view)
            if counter is not None:
                await interaction.channel.send(
                    f"{interaction.user} pressed a button, setting the counter to {counter}!"
                )

        if interaction.custom_id.startswith("btn reply test"):
            if await self.bot.is_owner(interaction.user):
                await interaction.response.send_message("You are the owner!", ephemeral=True)
            else:
                await interaction.response.send_message("You are not the owner!", ephemeral=True)
