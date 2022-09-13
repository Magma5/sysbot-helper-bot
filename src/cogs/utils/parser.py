from contextlib import suppress
import discord
import frontmatter

from sysbot_helper.utils import apply_obj_data


class DiscordTextParser:
    def __init__(self, text):
        post = frontmatter.loads(text)

        self._post = post
        self.headers = post.to_dict()

        self.content = self.headers.pop('content')
        self.command_options = self.headers.pop('command', {})
        self.message_content = self.headers.pop('text', None)

        self.split_text()

    def split_text(self):
        self._fields = ''

        # Find description/fields split
        content_split = self.content.split('\n\n\n', 1)
        with suppress(IndexError):
            self.description = content_split[0].strip()
            self._fields = content_split[1]

    @property
    def fields(self):
        return list(self.iter_fields())

    def iter_fields(self):
        field_sections = self._fields.split('\n\n')
        for section in field_sections:
            lines = section.strip()
            if lines:
                split = lines.split('\n')
                name = split[0]
                value = '\n'.join(split[1:])
                if name and value:
                    yield name, value

    def make_response(self, **kwargs):
        if 'title' not in self._post.keys():
            return {'content': self.content}
        return {
            'content': self.message_content,
            'embed': self.make_embed(**kwargs)
        }

    def make_embed(self, **attr):
        params = {
            'description': self.description
        }
        params.update(self.headers)
        params.update(attr)

        params_special = {k: v for k, v in params.items()
                          if k.startswith('set_') and isinstance(v, (dict, list))}

        embed = discord.Embed.from_dict(params)
        # embed = discord.Embed(**params_direct)

        # Apply special dict or list values
        apply_obj_data(embed, params_special)

        for name, value in self.iter_fields():
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
