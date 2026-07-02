import asyncio

import discord
import psutil
from discord import (
    ButtonStyle,
    SelectOption,
    slash_command,
    ui,
)
from discord.ext import commands

support2 = "https://mewtwo.party/"

sysbotval = str("""
 ⋅ testtradetest `<eb8>`: Request a pokemon from the bot.
 ⋅ guide: Shows a video on how to use SysBot.
 ⋅ languide: Shows instructions on how to download LAN play.
 ⋅ lgpe: Shows a video on how to use the LGPE SysBot.
 ⋅ queue: Sends you current queue position.
 ⋅ queue list: Displays the total queue list.
 ⋅ queue leave: Requests to leave the queue.
""")

filesval = str("""
 ⋅ pk8 `<pokemon>`: Sends a `pk8` file.
 ⋅ ek8 `<pokemon>`: Sends a `ek8` file.
 ⋅ pk7 `<pokemon>`: Sends a `pk7` file.
 ⋅ pk6 `<pokemon>`: Sends a `pk6` file.
 ⋅ pb8 `<pokemon>`: Sends a `eb8` file.
 ⋅ eb8 `<pokemon>`: Sends a `eb8` file.
 ⋅ pb7 `<pokemon>`: Sends a `pb7` file.
""")

miscellaneousval = str("""
 ⋅ prefix: Fetches the bot's prefix.
 ⋅ latency: Reports latency.
 ⋅ invite: Sends invite link to bot's home server.
 ⋅ support: Sends bot's donation link.
 ⋅ vote: Vote for a SysBot mode.
 ⋅ votelock: 3 votes will lock the channel the command is used in.
 ⋅ addcode: Saves your friend code.
 ⋅ fcode: Shows saved your friend code.
 ⋅ changecode: Changes your friend code.
 ⋅ removecode: Deletes your friend code.
""")

chanval = str("""
 ⋅ lock: Prevents members from type in used channel.
 ⋅ unlock: Allows members from type in used channel.
 ⋅ say <message>: Sends invite link to bot's home server.
 ⋅ purge <amount>: Bot repeats message.
 ⋅ slowmode <amount>: Changes the slowmode of used channel.
 ⋅ add: Adds channel to bot's announcement notification list.
 ⋅ remove: Removes channel from bot's announcement notification list.
""")

modval = str("""
 ⋅ kick  <member> (reason): Kicks mentioned member.
 ⋅ ban  <member> (reason): Bans mentioned member.
 ⋅ shareban <member> (reason): Bans mentioned member and announces in all linked channels.
 ⋅ unban <member>: Unbans mentioned member.
 ⋅ userinfo <member>: Displays mentioned member's info.
 ⋅ warn <member> <reason>: Warns mentioned member.
 ⋅ addrole <member> <role>: Gives mentioned member a role.
 ⋅ removerole <member> <role>: Removes mentioned member a role.
 ⋅ mute <member> <duration> (reason): Mutes mentioned member for said duration.
 ⋅ unmute <member>: Unmutes member.
 ⋅ category <channel> <category>: Moves the channels category location.
 ⋅ addban: Adds channel to bot's shareban notification list.
 ⋅ removeban: Removes channel from bot's shareban notification list.
""")

remoteval = str("""
 ⋅ click (x, a, b, or y): Tells switch to click selected button.
 ⋅ spamb: Tells switch to spam press the b button.
 ⋅ click (up, right, down, left): Tells switch which direction to move.
 ⋅ click (plus. minus, home): Clicks selected hotkey on switch.
 ⋅ pokemon (inject, dump): Dumps or injects pokemon into box 1 slot 1.
 ⋅ screen (on, off, shot, capture, percent): Controls the switch screen.
 ⋅ reconnect: Attempts to reconnect to your switch.
""")

ownerval = str("""
 ⋅ boton <message>: Sends a bot online message.
 ⋅ announcment <message>: Sends an announcement message.
 ⋅ botdown <message>: Sends a bot offline message.
 ⋅ redact <amount>: Redacts desired amount of announcement messages.
 ⋅ addsudo <member>: Adds member to sudo list.
 ⋅ removesudo <member>: Removes member from sudo list.
 ⋅ blacklist <member>: Saves your friend code.
 ⋅ unblacklist <member>: Shows saved your friend code.
 ⋅ loghere: Adds channel to logging output.
 ⋅ dontlog: Removes channel from logging output.
""")

botmanval = str("""
 ⋅ directmessage <userid> <content>: Sends message to directed user.
 ⋅ send <channelid> <content>: Sends message to directed channel.
 ⋅ list: List all servers the bot is in, including name, guild ID, owner, and invite.
 ⋅ leave <guildid>: Leaves server from directed guild.
 ⋅ createguild <name>: Creates a guild.
 ⋅ deleteguild <guildid>: Deletes an owned guild.
 ⋅ rename <name>: Renames the bot's name.
 ⋅ repfp <image>: Change the bot's pfp.
 ⋅ botinvite: Generates a bot invite.
 ⋅ load <cog>: Loads a cog.
 ⋅ reload <cog>: Reloads a cog.
 ⋅ unload <cog>: Unloads a cog.
 ⋅ restart: Restarts the bot.
 ⋅ shutdown: Turns off the bot.
""")

ttr = str("""
```yaml
Required Parameter: <> - Optional Parameter: ()
```
""")

# Help builder


class Helptest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_opening_note(self):
        return ()

    @slash_command()
    async def send_pages(self, ctx):
        help = discord.Embed(description=ttr, color=ctx.author.color)

        # Embeds
        embed = discord.Embed(
            title=f"{ctx.me.name} Commands",
            description=f"Utilize the dropdown menu to select help pages.{ttr}",
            color=ctx.author.color,
        )
        embed.add_field(
            name="💁 **Help Modules:**",
            value="Page 1 | SysBot Commands\nPage 2 | Pokemon Files Commands\nPage 3 | Miscellaneous Commands\nPage 4 | Management Commands\nPage 5 | Moderation Commands\nPage 6 | Switch Commands\nPage 7 | Owner Commands\nPage 8 | Bot Management Commands",
            inline=True,
        )
        embed.add_field(
            name="ℹ️ **Bot Info:**",
            value=f"Servers: {len(ctx.bot.guilds)}\nUsers: {len(ctx.bot.users)}\nCommands: {len(ctx.bot.commands)}\nCPU: {psutil.cpu_percent()}%\nMemory: {psutil.virtual_memory().percent}%",
            inline=True,
        )

        sysbot = discord.Embed(
            title="SysBot Module", description=ttr, color=ctx.author.color
        )
        sysbot.add_field(name="SysBot Commands", value=sysbotval, inline=True)

        files = discord.Embed(
            title="Files Module", description=ttr, color=ctx.author.color
        )
        files.add_field(name="Pkx and Ekx Search Commands", value=filesval, inline=True)

        general = discord.Embed(
            title="Miscellaneous Module", description=ttr, color=ctx.author.color
        )
        general.add_field(name="General Commands", value=miscellaneousval, inline=True)

        amanagement = discord.Embed(
            title="Channel Management Module", description=ttr, color=ctx.author.color
        )
        amanagement.add_field(name="Channel Commands", value=chanval, inline=True)

        moderation = discord.Embed(
            title="Moderation Module", description=ttr, color=ctx.author.color
        )
        moderation.add_field(
            name="Server Moderation Commands", value=modval, inline=True
        )

        sremote = discord.Embed(
            title="Switch Module", description=ttr, color=ctx.author.color
        )
        sremote.add_field(
            name="Switch Remote Control Commands", value=remoteval, inline=True
        )

        owner = discord.Embed(
            title="Owner Module", description=ttr, color=ctx.author.color
        )
        owner.add_field(name="Owner Only Commands", value=ownerval, inline=True)

        omanagement = discord.Embed(
            title="Bot Management Module", description=ttr, color=ctx.author.color
        )
        omanagement.add_field(
            name="Bot Management Commands", value=botmanval, inline=True
        )

        select1 = ui.Select(
            placeholder="Select a help menu",
            options=[
                SelectOption(label="All SysBot.py Commands", value="allcommands"),
                SelectOption(label="Page 1 | SysBot Module", value="sysbot"),
                SelectOption(label="Page 2 | Files Module", value="files"),
                SelectOption(label="Page 3 | Miscellaneous Module", value="general"),
                SelectOption(
                    label="Page 4 | Channel Management Module", value="amanagement"
                ),
                SelectOption(label="Page 5 | Moderation Module", value="moderation"),
                SelectOption(label="Page 6 | Switch Remote Module", value="sremote"),
                SelectOption(label="Page 7 | Owner Module", value="owner"),
                SelectOption(
                    label="Page 8 | Bot Management Module", value="omanagement"
                ),
            ],
            custom_id="6A-helptest",
        )
        button1 = ui.Button(
            label="Support Server", style=ButtonStyle.link, url=support2
        )

        view = ui.View()
        view.add_item(select1)
        view.add_item(button1)

        message = await ctx.respond(embed=embed, view=view)

        while True:
            try:
                interaction = await ctx.bot.wait_for(
                    "select_option", check=None, timeout=30
                )
                if interaction.values[0] == "allcommands":
                    await interaction.respond(type=7, ephemeral=False, embed=help)
                if interaction.values[0] == "sysbot":
                    await interaction.respond(type=7, ephemeral=False, embed=sysbot)
                if interaction.values[0] == "files":
                    await interaction.respond(type=7, ephemeral=False, embed=files)
                if interaction.values[0] == "general":
                    await interaction.respond(type=7, ephemeral=False, embed=general)
                if interaction.values[0] == "amanagement":
                    await interaction.respond(
                        type=7, ephemeral=False, embed=amanagement
                    )
                if interaction.values[0] == "moderation":
                    await interaction.respond(type=7, ephemeral=False, embed=moderation)
                if interaction.values[0] == "sremote":
                    await interaction.respond(type=7, ephemeral=False, embed=sremote)
                if interaction.values[0] == "owner":
                    await interaction.respond(type=7, ephemeral=False, embed=owner)
                if interaction.values[0] == "omanagement":
                    await interaction.respond(
                        type=7, ephemeral=False, embed=omanagement
                    )
            except asyncio.TimeoutError:
                await message.disable_components()
                return

    async def send_error_message(self):
        return
