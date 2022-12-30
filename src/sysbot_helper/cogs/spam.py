# Credit: https://github.com/menzi11/BullshitGenerator/pull/25/files
from yaml import safe_load
from random import choice, random
from dataclasses import dataclass
from discord.ext import commands
from discord import TextChannel
from time import time
from random import randint
import asyncio

from . import CogSendError


@dataclass
class BullshitData:
    bullshits: list[str]
    quote_1: list[str]
    quote_2: list[str]
    addings: list[str]
    examples: list[str]
    contrasts: list[str]
    suffix: list[str]
    author: list[str]
    saying: list[str]

    @property
    def quotes(self):
        return list(zip(self.author, self.saying))

    @classmethod
    def from_file(cls, fn="res/spam.yml"):
        with open(fn) as f:
            data = safe_load(f)
        return cls(**{k: v.strip().split("\n") for k, v in data.items()})


class BullshitGenerator:
    SENTENCE_ENDING = set(".?!")

    def __init__(self, data: BullshitData):
        self.data = data

    def saying(self):
        author, quote = choice(self.data.quotes)
        if random() > 0.3:
            return [author, choice(self.data.quote_1), quote, choice(self.data.suffix)]
        return [
            choice(self.data.quote_2),
            f"{author},",
            quote,
            choice(self.data.suffix),
        ]

    def sentence(self, theme):
        sentence = []
        if random() < 0.2:
            return [choice(self.data.examples)] + self.saying()

        if random() < 0.55:
            sentence.append(choice(self.data.addings))
        else:
            sentence.append(choice(self.data.contrasts))

        while sentence[-1][-1] not in self.SENTENCE_ENDING:
            sentence.append(choice(self.data.bullshits).format(topic=theme))

        return sentence

    def generate_sentence(self, theme, length):
        for _ in range(length):
            s = self.sentence(theme)
            s[0] = s[0].capitalize()
            yield " ".join(s)

    def generate_text(self, theme, length):
        return " ".join(self.generate_sentence(theme, length))


class Spam(CogSendError):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def spam(self, ctx, channel: TextChannel = None, count: int = 1):
        channel = channel or ctx.channel
        last_update = time()
        if count >= 10:
            updates = await ctx.send(f"Spamming {channel.name}... Progress: 0/{count}")
        generator = BullshitGenerator(BullshitData.from_file())

        for i in range(count):
            if count >= 10 and time() - last_update > 10:
                last_update = time()
                await updates.edit(
                    f"Spamming #{channel.name}... Progress: {i + 1}/{count}"
                )

            message = generator.generate_text("sysbot", randint(2, 8))
            await channel.send(message.strip())
            await asyncio.sleep(0.5)

        if count >= 10:
            await updates.edit(
                f"Spamming {channel.name}... Progress: {i + 1}/{count} Done!"
            )
