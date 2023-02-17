from typing import Any


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
