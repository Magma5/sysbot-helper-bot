from aiohttp import web

from sysbot_helper.bot import Bot


async def send_to_channel(bot: Bot, channel_id: int, **kwargs) -> dict:
    channel = bot.get_channel(channel_id)
    if not channel:
        raise web.HTTPNotFound(reason=f"Channel {channel_id} not found.")

    message = await channel.send(**kwargs)

    return {
        "message": {
            "id": message.id,
            "channel_id": message.channel.id,
            "content": message.content,
        }
    }
