import discord
import yaml
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from random import Random
from struct import Struct
import asyncio


def get_luck(num, now, mu=80, sigma=9):
    st = Struct('<Q')
    day = now.replace(tzinfo=timezone.utc).timestamp() // 86400
    seed_num = st.pack(num)
    seed_day = st.pack(int(day))
    seed = b'luck\x00\x00\x00\x00' + seed_num + seed_day
    rand = Random(seed)
    return rand.gauss(mu, sigma)


def get_now(tz_list):
    if type(tz_list) is str:
        tz_list = [tz_list]
    zones = [ZoneInfo(zone) for zone in tz_list]
    now = datetime.now(timezone.utc)
    result = { 'now': now.astimezone(zones[0]) }
    result.update({
        f'now_{zone.key.replace("/", "_")}':
        now.astimezone(zone)
        for zone in zones})
    return result


async def run(bot_config):
    bot = discord.Bot()

    @bot.event
    async def on_ready():
        for guild_id, guild_config in bot_config['guilds'].items():
            guild = await bot.fetch_guild(guild_id, with_counts=True)
            tz_config = guild_config.get('timezone', 'UTC')

            now_all = get_now(tz_config)
            now = now_all['now']
            yesterday = now - timedelta(days=1)

            # Calculate luck
            luck_today = get_luck(guild_id, now)
            luck_yesterday = get_luck(guild_id, yesterday)
            luck_diff = luck_today - luck_yesterday

            for channel_id, channel_template in guild_config['channels'].items():
                channel = await guild.fetch_channel(channel_id)
                channel_text = channel_template.format(
                    member_count=guild.approximate_member_count,
                    luck=luck_today,
                    luck_yesterday=luck_yesterday,
                    luck_diff=luck_diff,
                    **now_all
                ).strip()

                if channel.name == channel_text:
                    continue

                print(guild_id, channel.name, '->', channel_text)
                try:
                    await asyncio.wait_for(channel.edit(name=channel_text), timeout=3)
                except asyncio.exceptions.TimeoutError as e:
                    print(guild_id, "timeout: ", str(e), channel.name)
        await bot.close()

    await bot.start(bot_config['token'])


async def run_bots():
    with open('stats.yml') as f:
        stats_config = yaml.safe_load(f)
    await asyncio.gather(*(run(bot) for bot in stats_config))

asyncio.run(run_bots())
