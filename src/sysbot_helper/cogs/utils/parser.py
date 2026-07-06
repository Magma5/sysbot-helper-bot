import re
from collections import defaultdict
from contextlib import suppress
from typing import Any

import discord
import frontmatter
from slugify import slugify

from sysbot_helper.utils import apply_obj_data, embed_from_dict


class Post:
    def __init__(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        self.content = content
        self.metadata = defaultdict(dict) | (metadata or {})

        self.command_options = self.metadata.pop("command", {})

        # Process key aliases
        with suppress(KeyError):
            self.command_options["description"] = self.metadata.pop("help-desc")
        with suppress(KeyError):
            self.command_options["aliases"] = self.metadata.pop("aliases").split(",")
        with suppress(KeyError):
            self.metadata["author"]["name"] = self.metadata.pop("author.name")
        with suppress(KeyError):
            self.metadata["author"]["url"] = self.metadata.pop("author.url")
        with suppress(KeyError):
            self.metadata["thumbnail"]["url"] = self.metadata.pop("thumbnail-url")
        with suppress(KeyError):
            self.metadata["image"]["url"] = self.metadata.pop("image-url")

        if isinstance(self.metadata.get("color"), str):
            self.metadata["color"] = int(self.metadata["color"], 16)

        self.repeat = self.metadata.pop("repeat", 1)

        # Process title
        self.title = self.metadata.get("title")
        self.menu_title = self.metadata.pop("menu_title", self.title)
        self.menu_id = self.metadata.pop("menu_id", None)
        if self.menu_title and not self.menu_id:
            self.menu_id = slugify(self.menu_title)

        # Process fields
        self.fields: list[tuple[str, str]] = []
        self.inline = self.metadata.pop("inline", True)

        if self.title is None:
            return

        if not self.metadata.pop("process_fields", True):
            self.description = self.content
            return

        # Find description/fields split
        description_delimiter = re.compile(r"\n{3,}")
        field_delimiter = re.compile(r"\n{2,}")
        content_split = description_delimiter.split(self.content, 1)
        self.description = content_split[0].strip()

        with suppress(IndexError):
            fields = content_split[1]
            for section in field_delimiter.split(fields):
                if not section:
                    continue

                split = section.split("\n", 1)
                if len(split) == 2:
                    self.fields.append((split[0], split[1]))

    def is_embed(self) -> bool:
        return "title" in self.metadata

    def make_embed(self, **attrs: Any) -> discord.Embed:
        if self.title is None:
            return discord.Embed(description=self.content)

        params = {"description": self.description} | self.metadata | attrs

        params_set = {k: v for k, v in params.items() if k.startswith("set_") and isinstance(v, dict | list)}

        embed = embed_from_dict(params)

        # Apply special dict or list values
        apply_obj_data(embed, params_set)

        for name, value in self.fields:
            embed.add_field(name=name, value=value, inline=self.inline)

        return embed


class DiscordTextParser:
    def __init__(self, text: str, fail_ok: bool = False) -> None:
        self.posts = self._load_posts(text)

    @property
    def command_options(self) -> dict[str, Any]:
        return self.metadata.get("command_options", {})

    @property
    def post(self) -> Post:
        return self.posts[0]

    @property
    def metadata(self) -> dict[str, Any]:
        return self.post.metadata

    @property
    def menu_id(self) -> str | None:
        return self.post.menu_id

    @property
    def menu_title(self) -> str | None:
        return self.post.menu_title

    def _load_posts(self, text: str) -> list[Post]:
        """Splits text into multi-frontmatter document chunks and parses each post cleanly."""
        lines = text.splitlines()
        post_chunks: list[str] = []
        current_chunk_lines: list[str] = []

        for i, line in enumerate(lines):
            is_boundary = line.strip() == "---"
            is_next_line_yaml_key = i + 1 < len(lines) and bool(re.match(r"^[a-zA-Z0-9_\-]+:\s*", lines[i + 1].strip()))

            if is_boundary and is_next_line_yaml_key and current_chunk_lines:
                chunk_str = "\n".join(current_chunk_lines).strip()
                if chunk_str:
                    post_chunks.append(chunk_str)
                current_chunk_lines = [line]
            else:
                current_chunk_lines.append(line)

        if current_chunk_lines:
            chunk_str = "\n".join(current_chunk_lines).strip()
            if chunk_str:
                post_chunks.append(chunk_str)

        posts: list[Post] = []
        for chunk in post_chunks:
            try:
                parsed = frontmatter.loads(chunk)
                posts.append(Post(content=parsed.content, metadata=parsed.metadata))
            except ValueError:
                posts.append(Post(content=chunk))

        return posts or [Post(content=text)]

    def make_response(self, **kwargs: Any) -> dict[str, Any]:
        content: list[str] = []
        embeds: list[discord.Embed] = []
        for post in self.posts:
            for _ in range(post.repeat):
                if not post.is_embed():
                    content.append(post.content)
                else:
                    embeds.append(post.make_embed(**kwargs))

        return {"content": "\n".join(content).strip(), "embeds": embeds}

    @classmethod
    def from_file(cls, filename: str) -> "DiscordTextParser":
        with open(filename, encoding="utf8") as f:
            data = f.read()

        return cls(data)

    @classmethod
    def convert_to_response(cls, text: str) -> dict[str, Any]:
        return cls(text).make_response()
