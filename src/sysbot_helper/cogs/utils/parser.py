from contextlib import suppress
import re

import discord
import frontmatter
from sysbot_helper.utils import apply_obj_data, embed_from_dict
from slugify import slugify
from collections import defaultdict


class Post:
    def __init__(self, content, metadata={}):
        self.content = content
        self.metadata = defaultdict(dict) | metadata

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

        if type(self.metadata.get("color")) is str:
            self.metadata["color"] = int(self.metadata["color"], 16)

        self.repeat = self.metadata.pop("repeat", 1)

        # Process title
        self.title = self.metadata.get("title")
        self.menu_title = self.metadata.pop("menu_title", self.title)
        self.menu_id = self.metadata.pop("menu_id", None)
        if self.menu_title and not self.menu_id:
            self.menu_id = slugify(self.menu_title)

        # Process fields
        self.fields = []
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
                    self.fields.append(split)

    def is_embed(self):
        return "title" in self.metadata

    def make_embed(self, **attrs):
        if self.title is None:
            return discord.Embed(description=self.content)

        params = {"description": self.description} | self.metadata | attrs

        params_set = {
            k: v
            for k, v in params.items()
            if k.startswith("set_") and isinstance(v, (dict, list))
        }

        embed = embed_from_dict(params)

        # Apply special dict or list values
        apply_obj_data(embed, params_set)

        for name, value in self.fields:
            embed.add_field(name=name, value=value, inline=self.inline)

        return embed


class DiscordTextParser:
    def __init__(self, text, fail_ok=False):
        self.posts = self._load_posts(text)

    @property
    def command_options(self):
        return self.metadata.get("command_options", {})

    @property
    def post(self):
        if len(self.posts) > 1:
            return self.posts[1]
        return self.posts[0]

    @property
    def metadata(self):
        return self.post.metadata

    @property
    def menu_id(self):
        return self.post.menu_id

    @property
    def menu_title(self):
        return self.post.menu_title

    def _load_posts(self, text):
        """Parse the given text as a list of multiple posts."""

        handlers = [
            frontmatter.JSONHandler,
            frontmatter.YAMLHandler,
            frontmatter.TOMLHandler,
        ]

        posts = []

        current_post = []
        current_handler = None

        for line in text.split("\n"):
            if current_handler is None:
                for handler in handlers:
                    if handler and handler.FM_BOUNDARY.match(line):
                        current_handler = handler
                        post = "\n".join(current_post)
                        current_post.clear()

                        try:
                            parsed = frontmatter.loads(post)
                            posts.append(Post(parsed.content, parsed.metadata))
                        except ValueError:
                            posts.append(Post(post))
                        break

            elif current_handler.FM_BOUNDARY.match(line):
                current_handler = None
            current_post.append(line)

        # Guarantee to have at least one post
        post = "\n".join(current_post)
        try:
            parsed = frontmatter.loads(post)
            posts.append(Post(parsed.content, parsed.metadata))
        except ValueError:
            posts.append(Post(post))

        return posts

    def make_response(self, **kwargs):
        content = []
        embeds = []
        for post in self.posts:
            for _ in range(post.repeat):
                if not post.is_embed():
                    content.append(post.content)
                else:
                    embeds.append(post.make_embed(**kwargs))

        return {"content": "\n".join(content).strip(), "embeds": embeds}

    @classmethod
    def from_file(cls, filename):
        with open(filename, encoding="utf8") as f:
            data = f.read()

        return cls(data)

    @classmethod
    def convert_to_response(cls, text):
        return cls(text).make_response()
