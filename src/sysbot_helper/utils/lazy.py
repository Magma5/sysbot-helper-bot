from collections.abc import Mapping
from typing import Any


class LazyContext(dict[str, Any]):
    """A dictionary wrapper used during Jinja2 template rendering that acts as a memoizing proxy.

    Capabilities:
    1. Lazy Evaluation: Deferred callables (functions/lambdas) are executed only upon first template access.
    2. Memoization: Evaluated values are cached in self[key] so subsequent reads are instant.
    3. Dynamic Mapping Support: Delegates un-memoized keys directly to source_mapping[key],
       preserving custom dict subclass behavior (e.g. TimeContext).
    """

    def __init__(self, source_mapping: Mapping[str, Any]) -> None:
        self._source_mapping: Mapping[str, Any] = source_mapping
        super().__init__()

    def __getitem__(self, key: str) -> Any:
        # Check if key is already cached in the dictionary storage
        if dict.__contains__(self, key):
            return super().__getitem__(key)

        # Retrieve value from underlying mapping (supports both dicts and dynamic dict subclasses)
        value: Any = self._source_mapping[key]

        # Lazily evaluate callable values
        if callable(value) and not isinstance(value, type):
            value = value()

        # Cache result for future reads in this rendering context
        self[key] = value
        return value

    def __contains__(self, key: object) -> bool:
        return super().__contains__(key) or key in self._source_mapping

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default
