import unittest
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError
from jinja2.sandbox import SecurityError
from sysbot_helper.templates import TemplateEngine


class TestTemplatesJinja(unittest.TestCase):
    def test_all_templates_compile_without_syntax_errors(self) -> None:
        """Recursively validates that all template files compile cleanly in Jinja2."""
        templates_directory: Path = Path("templates")
        if not templates_directory.exists():
            self.skipTest("Templates directory does not exist in workspace.")

        environment: Environment = Environment(loader=FileSystemLoader("templates"))
        template_paths: list[Path] = [
            path
            for path in templates_directory.glob("**/*")
            if path.is_file() and path.suffix in (".md", ".txt", ".html", ".yml")
        ]

        failed_templates: list[tuple[str, str]] = []
        for template_path in template_paths:
            relative_path_string: str = template_path.relative_to(templates_directory).as_posix()
            try:
                environment.get_template(relative_path_string)
            except TemplateSyntaxError as syntax_error:
                failed_templates.append((relative_path_string, str(syntax_error)))
            except Exception as general_exception:
                failed_templates.append((relative_path_string, str(general_exception)))

        self.assertEqual(
            len(failed_templates),
            0,
            "The following template files failed to compile:\n"
            + "\n".join(f"{path}: {error}" for path, error in failed_templates),
        )

    def test_sandboxed_template_engine_prevents_ssti_exploitation(self) -> None:
        """Verifies that SandboxedEnvironment blocks unsafe Python attribute access."""
        template_engine: TemplateEngine = TemplateEngine()
        dangerous_template_string: str = "{{ ''.__class__.__mro__[1].__subclasses__() }}"

        with self.assertRaises(SecurityError):
            template_engine.render_string(dangerous_template_string, {})

    def test_template_custom_filters(self) -> None:
        """Verifies custom filters (strftime, regex_replace, truncate_length)."""
        template_engine: TemplateEngine = TemplateEngine()
        test_datetime: datetime = datetime(2026, 7, 1, 12, 0, 0)

        formatted_date: str = template_engine.render_string(
            "{{ target_datetime | strftime('%Y-%m-%d') }}",
            {"target_datetime": test_datetime},
        )
        self.assertEqual(formatted_date, "2026-07-01")

        replaced_string: str = template_engine.render_string(
            "{{ 'hello 123' | regex_replace('[0-9]+', 'world') }}",
            {},
        )
        self.assertEqual(replaced_string, "hello world")

        truncated_string: str = template_engine.render_string(
            "{{ ('a' * 10) | truncate_length(5) }}",
            {},
        )
        self.assertEqual(truncated_string, "aa...")
