from discord import slash_command, File
from discord.ext import commands
from discord.commands.options import Option
from discord.errors import ApplicationCommandInvokeError

from dataclasses import dataclass
import asyncio
import logging
from io import BytesIO
import mss
from PIL import Image


class Sysbot(commands.Cog):
    @dataclass
    class Config:
        ip: str
        port: int

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @commands.Cog.listener()
    async def on_ready(self):
        await self.connect()

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.respond(f"Check failure: {str(error)}")
            return

        if isinstance(error, ApplicationCommandInvokeError):
            cause = error.__cause__
            if isinstance(cause, (ConnectionError, AttributeError)):
                # Reply the name of the error
                msg = f"Connection to switch may be down. Try again later.\nError: {cause.__class__.__name__}"
                await ctx.send(msg)

                # Try to reconnect and recover the connection
                await self.connect()

        raise error

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.config.ip, self.config.port)

    async def send_command(self, *args):
        logging.info('Send switch command: %s', repr(args))
        cmd = ' '.join(args) + '\r\n'
        self.writer.write(cmd.encode('utf-8'))
        await self.writer.drain()

    @slash_command()
    @commands.is_owner()
    async def screen(self, ctx,
                     action: Option(str, "Action for screen, on or off", choices=['on', 'off'], required=True),
                     delay: Option(int, "Number of seconds to wait before running the command", default=0, required=False)):
        # Check if command needs schedule
        if delay > 0:
            await ctx.respond(f'Screen command is scheduled to run after {delay} seconds.')
            await asyncio.sleep(delay)
        else:
            await ctx.respond('Screen command will run shortly.')
            await asyncio.sleep(1)

        # Send the command
        command = 'screen' + action.capitalize()
        await self.send_command(command)
        await ctx.send(f'Your screen has been turned {action}.')

    @slash_command()
    @commands.is_owner()
    async def screenshot(self, ctx):
        monitor_index = 1

        # Grab the screen
        with mss.mss() as sct:
            monitor = sct.monitors[monitor_index]
            screen = sct.grab(monitor)

        # Create raw PIL object
        img = Image.frombytes('RGB', screen.size, screen.bgra, "raw", "BGRX")

        # Save as JPG
        data = BytesIO()
        img.save(data, format='jpeg', quality=60)

        # Send data to discord
        data.seek(0)
        file = File(data, filename="screen.jpg")
        await ctx.respond(file=file)
