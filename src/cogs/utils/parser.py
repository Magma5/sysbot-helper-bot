from contextlib import suppress

import discord
import frontmatter
from sysbot_helper.utils import apply_obj_data, embed_from_dict


class DiscordTextParser:
    def __init__(self, text, fail_ok=False):
        self.text = text
        self.post = None

        try:
            self.post = frontmatter.loads(text)
        except Exception:
            if fail_ok:
                return
            raise

        self.headers = {
            'author': {},
            'thumbnail': {}
        }

        self.headers.update(self.post.metadata)

        self.command_options = self.headers.pop('command', {})
        self.message_content = self.headers.pop('text', None)

        help_desc = self.headers.pop('help-desc', None)
        aliases = self.headers.pop('aliases', None)
        author_name = self.headers.pop('author.name', None)
        author_url = self.headers.pop('author.url', None)
        thumbnail_url = self.headers.pop('thumbnail-url', None)

        if help_desc:
            self.command_options['description'] = help_desc
        if aliases:
            self.command_options['aliases'] = aliases.split(',')
        if author_name:
            self.headers['author']['name'] = author_name
        if author_url:
            self.headers['author']['url'] = author_url
        if thumbnail_url:
            self.headers['thumbnail']['url'] = thumbnail_url

        self.split_fields()

    def split_fields(self):
        self.fields = []

        # Find description/fields split
        content_split = self.post.content.split('\n\n\n', 1)
        self.description = content_split[0].strip()

        with suppress(IndexError):
            fields = content_split[1]
            for section in fields.split('\n\n'):
                lines = section.strip()
                if lines:
                    split = lines.split('\n')
                    name = split[0]
                    value = '\n'.join(split[1:])
                    if name and value:
                        self.fields.append((name, value))

    def make_response(self, **kwargs):
        if self.post is None or 'title' not in self.headers:
            return {'content': self.text}
        return {
            'content': self.message_content,
            'embed': self.make_embed(**kwargs)
        }

    def make_embed(self, **attr):
        if self.post is None:
            return discord.Embed(description=self.text)

        params = {
            'description': self.description
        }
        params.update(self.headers)
        params.update(attr)

        params_set = {k: v for k, v in params.items()
                      if k.startswith('set_') and isinstance(v, (dict, list))}

        embed = embed_from_dict(params)

        # Apply special dict or list values
        apply_obj_data(embed, params_set)

        for name, value in self.fields:
            embed.add_field(name=name, value=value, inline=True)

        return embed

    @classmethod
    def from_file(cls, filename):
        with open(filename, encoding='utf8') as f:
            data = f.read()

        return cls(data)

    @classmethod
    def convert_to_embed(cls, text):
        parser = cls(text)
        return parser.make_embed()

    @classmethod
    def convert_to_response(cls, text):
        parser = cls(text)
        return parser.make_response()
