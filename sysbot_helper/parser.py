from contextlib import suppress
import yaml
import discord


class DiscordTextParser:
    def __init__(self, text, parse=True):
        self._text = text
        if parse:
            self.split_text()

    def split_text(self):
        headers, fields = "", ""

        # Find headers first
        headers_split = self._text.split('---\n', 1)
        if len(headers_split) == 1:
            content = headers_split[0]
        else:
            headers, content = headers_split[1].split('---', 1)

        # Find description/fields split
        content_split = content.split('\n\n\n', 1)
        with suppress(IndexError):
            description = content_split[0]
            fields = content_split[1]

        self._headers = headers
        self._description = description
        self._fields = fields

    @property
    def headers(self):
        return yaml.safe_load(self._headers)

    @property
    def description(self):
        return self._description.strip()

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
        if not self.headers:
            return {'content': self.description}
        return {'embed': self.make_embed(**kwargs)}

    def make_embed(self, **attr):
        headers = attr
        headers.update(self.headers)
        params = {k: v for k, v in headers.items()
                  if not isinstance(v, (dict, list))}
        embed = discord.Embed(description=self.description, **params)

        for key in headers.keys() - params.keys():
            args_list = headers[key]

            # Load the embed method given method name
            if not hasattr(embed, key):
                continue
            method = getattr(embed, key)

            # Determine if calling method multiple times
            if isinstance(args_list, dict):
                args_list = [args_list]

            # Apply the given method
            for item in args_list:
                method(**item)

        for name, value in self.iter_fields():
            embed.add_field(name=name, value=value, inline=True)

        return embed

    @classmethod
    def from_file(cls, filename, **args):
        with open(filename, encoding='utf8') as f:
            data = f.read()

        return cls(data, **args)

    @classmethod
    def convert_embed(cls, text):
        parser = cls(text)
        return parser.make_embed()
