import json
from functools import cache
from html.parser import HTMLParser
from io import BytesIO, StringIO

import anyio
from discord import Embed, File
from discord.ext import commands
from PIL import Image


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


class Adb(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def screenshot(self):
        data = await anyio.run_process("adb exec-out screencap -p")
        return data

    @commands.command()
    async def sc(self, ctx):
        output = await self.screenshot()

        img = Image.open(BytesIO(output.stdout))
        screen = BytesIO()
        img.convert("RGB").save(screen, format="jpeg", quality=60)
        screen.seek(0)

        screen_file = File(screen, filename="screen.jpg")
        embed = Embed(title="Embed")
        embed.set_image(url="attachment://screen.jpg")

        await ctx.send(embed=embed, file=screen_file)

    @cache
    def load_titleid(self):
        with open("res/titledb/titles.json") as f:
            data = json.load(f)
        return data

    @commands.command()
    async def titleid(self, ctx, titleid: str):
        data = self.load_titleid()
        id = titleid.upper()
        if id not in data:
            return await ctx.send("Title ID not found")

        title = data[id]

        embed = Embed(title=strip_tags(title["name"]))
        if title["description"]:
            embed.description = title["description"]
        embed.set_thumbnail(url=title["iconUrl"])
        embed.add_field(name="Title ID", value=title["id"], inline=False)
        embed.add_field(name="Release date", value=title["releaseDate"], inline=False)
        embed.add_field(name="Publisher", value=title["publisher"], inline=False)
        embed.add_field(name="size", value=title["size"], inline=False)

        await ctx.send(embed=embed)
