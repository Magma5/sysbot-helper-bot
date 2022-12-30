from typing import Any
from discord import Embed
from iso8601 import iso8601


def apply_obj_data(obj: Any, data: dict):
    """Apply method calls to obj from input data."""

    for key, val in data.items():
        if not hasattr(obj, key):
            continue

        # Filter calls to private methods
        if key.startswith("_"):
            continue

        method = getattr(obj, key)

        # Determine if calling method multiple times
        if isinstance(val, dict):
            val = [val]

        # Apply the method one by one
        for item in val:
            method(**item)


def embed_from_dict(data_raw):
    data = {k: v for k, v in data_raw.items() if v is not None}

    if "timestamp" in data:
        data["timestamp"] = iso8601.parse_date(data["timestamp"]).isoformat()

    return Embed.from_dict(data)
