import unittest
from sysbot_helper.cogs.utils.parser import DiscordTextParser, Post


class TestDiscordTextParser(unittest.TestCase):
    def test_discord_text_parser_frontmatter_single_post(self) -> None:
        """Verifies parsing of single post with frontmatter metadata."""
        raw_document_text: str = """---
title: Welcome Announcement
repeat: 2
command:
  description: Shows welcome menu
---
Hello user, welcome to the server!
"""
        parser: DiscordTextParser = DiscordTextParser(raw_document_text)

        self.assertEqual(len(parser.posts), 1)
        post: Post = parser.post
        self.assertEqual(post.title, "Welcome Announcement")
        self.assertEqual(post.repeat, 2)
        self.assertEqual(post.command_options.get("description"), "Shows welcome menu")
        self.assertEqual(post.content.strip(), "Hello user, welcome to the server!")

    def test_discord_text_parser_multi_post_split(self) -> None:
        """Verifies splitting multi-document frontmatter into separate posts."""
        raw_document_text: str = """---
title: First Post
---
First post content line.

---
title: Second Post
---
Second post content line.
"""
        parser: DiscordTextParser = DiscordTextParser(raw_document_text)

        self.assertEqual(len(parser.posts), 2)
        self.assertEqual(parser.posts[0].title, "First Post")
        self.assertEqual(parser.posts[1].title, "Second Post")
