import asyncio
import json
import logging
import re
from dataclasses import dataclass, field

from discord.channel import TextChannel
from discord.ext import commands
from minecraft.networking.connection import Connection
from minecraft.networking.packets import clientbound, serverbound
from minecraft.networking.packets.packet import Packet

log = logging.getLogger(__name__)


class MinecraftTextParser:
    MINECRAFT_LANG_JSON = "res/minecraft/lang/en_us.json"

    def __init__(self):
        self.lang = {}
        try:
            with open(self.MINECRAFT_LANG_JSON) as f:
                self.lang = json.load(f)
        except FileNotFoundError:
            log.info("Minecraft language file not found at %s.", self.MINECRAFT_LANG_JSON)

    def parse(self, json_data):
        data = json.loads(json_data)
        text = self.parse_json_obj(data)
        if isinstance(text, list):
            return "".join(text)
        return text

    def parse_json_obj(self, data):
        if isinstance(data, list):
            return [self.parse_json_obj(a) for a in data]
        elif isinstance(data, dict):
            text = data.get("text", "")
            if "translate" in data:
                translate = data["translate"]
                text = self.lang.get(translate, translate)
                translate_with = data.pop("with", [])
                subst = self.parse_json_obj(translate_with)

                text, nsubs = re.subn(r"%([0-9]+)\$", r"%(\1)", text)
                if nsubs > 0:
                    text = text % {str(i + 1): content for i, content in enumerate(subst)}
                else:
                    text = text % tuple(subst)
            text += "".join(self.parse_json_obj(data.get("extra", [])))
            return text
        else:
            return str(data)


@dataclass
class MinecraftSession:
    connection: Connection
    channel: TextChannel
    user: int
    messages: list = field(default_factory=list)
    lock: asyncio.Lock = asyncio.Lock()
    health: Packet = None
    respawn: Packet = None
    position_and_look: Packet = None


class Minecraft(commands.Cog):
    @dataclass
    class Config:
        servers: dict

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.connections = {}
        self.messages = {}
        self.parser = MinecraftTextParser()

    @commands.group(name="minecraft", aliases=("mc",))
    async def mc(self, ctx):
        pass

    @mc.command()
    async def status(self, ctx):
        session = self.connections.get(ctx.channel.id, None)
        if session and session.user == ctx.author.id:
            content = []
            if session.health:
                content.append(
                    "Health: %.1f, Food: %d, Saturation: %.1f"
                    % (
                        session.health.health,
                        session.health.food,
                        session.health.food_saturation,
                    )
                )
            if session.position_and_look:
                pos = session.position_and_look
                content.append(f"X: {pos.x:.1f}, Y: {pos.y:.1f}, Z: {pos.z:.1f}")

            await ctx.send("\n".join(content))
        else:
            await ctx.send("You are not connected to a Minecraft server!")

    @mc.command()
    async def login(self, ctx):
        ip = self.config.servers["default"]["ip"]
        port = self.config.servers["default"]["port"]

        def handle_exception(exc, exc_info):
            self.bot.loop.create_task(session.channel.send(f"Exception occured in Minecraft connection: {str(exc)}"))
            self.connections.pop(ctx.channel.id)

        def handle_exit():
            self.bot.loop.create_task(session.channel.send("Connection to Minecraft has been closed."))
            self.connections.pop(ctx.channel.id)

        connection = Connection(
            ip,
            port,
            username="SysbotHelper",
            handle_exception=handle_exception,
            handle_exit=handle_exit,
        )
        session = MinecraftSession(connection, ctx.channel, ctx.author.id)
        self.connections[ctx.channel.id] = session

        def handle_chat(chat_packet):
            self.bot.loop.create_task(self.handle_chat_async(session, chat_packet))

        def handle_join(join_game_packet):
            self.bot.loop.create_task(self.handle_join_async(session, join_game_packet))

        def handle_health(update_health_packet):
            session.health = update_health_packet

        def handle_respawn(respawn_packet):
            session.respawn = respawn_packet

        def handle_position_and_look(position_and_look_packet):
            session.position_and_look = position_and_look_packet

        connection.register_packet_listener(handle_chat, clientbound.play.ChatMessagePacket)
        connection.register_packet_listener(handle_join, clientbound.play.JoinGamePacket)
        connection.register_packet_listener(handle_health, clientbound.play.UpdateHealthPacket)
        connection.register_packet_listener(handle_respawn, clientbound.play.RespawnPacket)
        connection.register_packet_listener(handle_position_and_look, clientbound.play.PlayerPositionAndLookPacket)

    @mc.command()
    async def chat(self, ctx, *, message):
        channel_id = ctx.channel.id
        if channel_id in self.connections:
            connection = self.connections[channel_id].connection
            packet = serverbound.play.ChatPacket()
            packet.message = message
            connection.write_packet(packet)

    @mc.command()
    async def respawn(self, ctx):
        channel_id = ctx.channel.id
        if channel_id in self.connections:
            connection = self.connections[channel_id].connection
            packet = serverbound.play.ClientStatusPacket()
            packet.action_id = serverbound.play.ClientStatusPacket.RESPAWN
            connection.write_packet(packet)
            await ctx.send("respawning...")

    async def handle_chat_async(self, session, chat_packet):
        message = "({}): {}".format(
            chat_packet.field_string("position"),
            self.parser.parse(chat_packet.json_data),
        )

        session.messages.append(message)
        if session.lock.locked():
            return

        async with session.lock:
            await asyncio.sleep(0.3)
            content = "\n".join(session.messages)
            session.messages.clear()
            await session.channel.send(content)

    async def handle_join_async(self, session, join_packet):
        await session.channel.send("Connected!")
