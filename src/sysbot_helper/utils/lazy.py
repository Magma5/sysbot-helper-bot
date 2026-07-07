class LazyContext(dict):
    """Dictionary-like context that evaluates callables lazily on first access."""

    def __getitem__(self, key):
        val = super().__getitem__(key)
        if callable(val) and not isinstance(val, type):
            val = val()
            self[key] = val
        return val

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
