from discord.ext.commands import Context
import asyncio


class DiscordMessage:
    def __init__(self, init=None):
        self.message = {}
        if init:
            self.update(init)

    def update(self, args):
        if isinstance(args, str):
            self.message['content'] = args
        else:
            self.message.update(args)

    async def send(self, ctx, variables):
        env = ctx.bot.template_env
        message = self.message

        # Render templates
        content = message.get('content', None)
        if content:
            message['content'] = env.from_string(content).render(variables)

        # Specify the channel to send to
        _channel = message.pop('channel', None)
        if _channel:
            channel = ctx.bot.get_channel(_channel)
        else:
            channel = ctx.channel

        return await channel.send(**message)


class DiscordAction:
    def __init__(self, ctx: Context, **variables):
        self.ctx = ctx
        self.bot = ctx.bot
        self.env = self.bot.template_env

        self.variables = self.bot.template_variables(ctx)
        self.variables.update(variables)

        self.sent_messages = []

    async def react(self, emoji):
        if isinstance(emoji, int):
            emoji = self.bot.get_emoji(emoji)
        await self.ctx.message.add_reaction(emoji)

    async def reply(self, text):
        discord_msg = DiscordMessage(text)
        discord_msg.update({'reference': self.ctx.message})
        msg = await discord_msg.send(self.ctx, self.variables)
        self.sent_messages.append(msg)

    async def send(self, text):
        discord_msg = DiscordMessage(text)
        msg = await discord_msg.send(self.ctx, self.variables)
        self.sent_messages.append(msg)

    async def delete(self, yes=True):
        if yes:
            await self.ctx.message.delete()

    async def delete_after(self, delay):
        await asyncio.sleep(delay)
        await self.delete()

    async def delete_replies_after(self, delay):
        await asyncio.sleep(delay)
        while self.sent_messages:
            msg = self.sent_messages.pop()
            await msg.delete()

    async def delay(self, delay):
        await asyncio.sleep(delay)

    async def suppress_embeds(self, yes):
        if yes:
            await self.ctx.message.edit(suppress=True)
