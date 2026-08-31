from typing import Any

from discord import Embed


def embed_from_dict(data_raw: dict[str, Any]) -> Embed:
    data = {k: v for k, v in data_raw.items() if v is not None}
    return Embed.from_dict(data)
