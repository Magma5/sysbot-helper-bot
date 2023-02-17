from discord import Embed
from iso8601 import iso8601


def embed_from_dict(data_raw):
    data = {k: v for k, v in data_raw.items() if v is not None}

    # Python doesn't recognize iso8601 formatted date
    if "timestamp" in data:
        data["timestamp"] = iso8601.parse_date(data["timestamp"]).isoformat()

    return Embed.from_dict(data)
