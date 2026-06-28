import unittest
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError


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
