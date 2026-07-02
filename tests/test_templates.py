import unittest
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError
from jinja2.sandbox import SecurityError

from sysbot_helper.templates import TemplateEngine


class TestTemplatesJinja(unittest.TestCase):
    def setUp(self):
        # Initialize the Jinja environment matching the Bot's initialization
        self.env = Environment(loader=FileSystemLoader("templates"))

    def test_all_templates_compile(self):
        """Recursively find all template files and verify they compile without Jinja syntax errors."""
        templates_root = Path("templates")
        self.assertTrue(templates_root.exists(), "Templates directory does not exist!")

        all_files = list(templates_root.glob("**/*"))
        template_files = [
            f
            for f in all_files
            if f.is_file() and f.suffix in (".md", ".txt", ".html", ".yml")
        ]

        print(f"Found {len(template_files)} templates to validate.")

        failed_templates = []
        for path in template_files:
            relative_path = path.relative_to(templates_root).as_posix()
            try:
                # This will load and compile the template in Jinja2
                self.env.get_template(relative_path)
            except TemplateSyntaxError as e:
                print(
                    f"FAILED to compile: {relative_path} - Line {e.lineno}: {e.message}"
                )
                failed_templates.append((relative_path, str(e)))
            except Exception as e:
                print(f"FAILED to load: {relative_path} - {str(e)}")
                failed_templates.append((relative_path, str(e)))

        self.assertEqual(
            len(failed_templates),
            0,
            "The following templates failed to compile:\n"
            + "\n".join(f"{p}: {err}" for p, err in failed_templates),
        )
        print("All templates successfully compiled by Jinja2!")

    def test_sandboxed_security(self):
        """Verify that SandboxedEnvironment prevents SSTI and dangerous attribute access."""
        engine = TemplateEngine()
        # Attempting to access __class__ or __subclasses__ in SandboxedEnvironment raises SecurityError
        with self.assertRaises(SecurityError):
            engine.render_string("{{ ''.__class__.__mro__[1].__subclasses__() }}", {})

    def test_custom_filters(self):
        """Verify strftime, regex_replace, and truncate_length custom filters."""
        engine = TemplateEngine()
        now = datetime(2026, 7, 1, 12, 0, 0)

        # strftime
        res = engine.render_string("{{ now | strftime('%Y-%m-%d') }}", {"now": now})
        self.assertEqual(res, "2026-07-01")

        # regex_replace
        res = engine.render_string("{{ 'hello 123' | regex_replace('[0-9]+', 'world') }}", {})
        self.assertEqual(res, "hello world")

        # truncate_length
        res = engine.render_string("{{ ('a' * 10) | truncate_length(5) }}", {})
        self.assertEqual(res, "aa...")
