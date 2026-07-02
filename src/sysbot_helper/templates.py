import functools
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment

log = logging.getLogger(__name__)


def _filter_strftime(value: Any, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if isinstance(value, datetime):
        return value.strftime(fmt)
    return str(value)


def _filter_regex_replace(value: str, pattern: str, replacement: str) -> str:
    return re.sub(pattern, replacement, str(value or ""))


def _filter_truncate_length(value: str, max_length: int = 2000) -> str:
    text = str(value or "")
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


class TemplateEngine:
    """Hardened Jinja2 template engine using SandboxedEnvironment and multi-loader support."""

    def __init__(
        self,
        template_dirs: Optional[list[Union[str, Path]]] = None,
        extra_templates: Optional[dict[str, str]] = None,
    ):
        loaders = []

        if extra_templates:
            loaders.append(DictLoader(extra_templates))

        if template_dirs:
            for t_dir in template_dirs:
                p = Path(t_dir)
                if p.is_dir():
                    loaders.append(FileSystemLoader(p))

        # Default fallback to 'templates' if it exists and wasn't already added
        default_dir = Path("templates")
        if default_dir.is_dir() and not any(
            Path(d).resolve() == default_dir.resolve() for d in (template_dirs or [])
        ):
            loaders.append(FileSystemLoader(default_dir))

        loader = ChoiceLoader(loaders) if len(loaders) > 1 else (loaders[0] if loaders else None)

        self.env = SandboxedEnvironment(
            loader=loader,
            autoescape=False,  # Generating Markdown/Plaintext for Discord, not HTML
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self.env.filters["strftime"] = _filter_strftime
        self.env.filters["regex_replace"] = _filter_regex_replace
        self.env.filters["truncate_length"] = _filter_truncate_length

    # Using @lru_cache on an instance method binds `self` in the cache key.
    # Because TemplateEngine is managed as a singleton on Bot, this is safe for lifetime reuse.
    # If TemplateEngine is ever instantiated dynamically per-request or per-cog, use an instance-dict cache instead.
    @functools.lru_cache(maxsize=256)
    def _compile_string(self, source: str):
        return self.env.from_string(source)

    def render_string(self, source: str, context: dict[str, Any]) -> str:
        """Render an inline Jinja2 template string using cached compiled AST."""
        template = self._compile_string(source)
        return template.render(context)

    def render_file(self, name: str, context: dict[str, Any]) -> str:
        """Render a file-based template from configured template loaders."""
        template = self.env.get_template(name)
        return template.render(context)
