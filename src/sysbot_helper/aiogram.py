from aiogram.types import Message
from aiogram.utils.text_decorations import \
    MarkdownDecoration as AIOGramMarkdownDecoration
from aiogram.utils.text_decorations import TextDecoration


class MarkdownDecoration(AIOGramMarkdownDecoration):
    """Fix aiogram's markdown decoration according to standard markdown."""
    def bold(self, value: str) -> str:
        return f"**{value}**"

    def italic(self, value: str) -> str:
        return f"*{value}*"

    def strikethrough(self, value: str) -> str:
        return f"~~{value}~~"

    def spoiler(self, value: str) -> str:
        return f"||{value}||"


markdown_decoration = MarkdownDecoration()


def unparse_entities(message: Message, text_decoration: TextDecoration = markdown_decoration) -> str:
    text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []
    return text_decoration.unparse(text=text, entities=entities)
