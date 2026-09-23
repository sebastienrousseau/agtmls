# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""validate-readme.py: README.md keeps the portfolio template's layout."""

from __future__ import annotations

from .subset_support import SubsetCase


class ReadmeTemplateTests(SubsetCase):
    SCRIPT = "validate-readme.py"
    SUBSET = ("README.md",)

    def setUp(self) -> None:
        self.preserve("README.md")
        self.readme = self.path("README.md")
        self.text = self.readme.read_text(encoding="utf-8")

    def rewrite(self, text: str) -> tuple[int, str]:
        self.readme.write_text(text, encoding="utf-8")
        return self.drive()

    def test_the_committed_readme_passes(self) -> None:
        code, output = self.drive()
        self.assertEqual(code, 0, output)
        self.assertIn("OK: README.md follows the template (17 sections, in order)", output)

    def test_an_unresolved_variable_is_refused(self) -> None:
        for token in ("{{PROJECT_NAME}}", "stray }}"):
            with self.subTest(token=token):
                code, output = self.rewrite(self.text + f"\n{token}\n")
                self.assertEqual(code, 1, output)
                self.assertIn("FAIL: README.md: unresolved template variables", output)

    def test_a_missing_title_is_refused(self) -> None:
        code, output = self.rewrite(self.text.replace('<h1 align="center">', "<h1>", 1))
        self.assertEqual(code, 1, output)
        self.assertIn("centered project h1 missing", output)

    def test_a_missing_and_an_invented_section_are_named(self) -> None:
        text = self.text.replace("\n## Examples\n", "\n## Tutorials\n", 1)
        code, output = self.rewrite(text)
        self.assertEqual(code, 1, output)
        self.assertIn("missing heading: Examples", output)
        self.assertIn("unexpected heading: Tutorials", output)

    def test_sections_out_of_order_are_refused(self) -> None:
        text = self.text.replace("\n## Install\n", "\n## TMP\n", 1)
        text = text.replace("\n## Requirements\n", "\n## Install\n", 1).replace("\n## TMP\n", "\n## Requirements\n", 1)
        code, output = self.rewrite(text)
        self.assertEqual(code, 1, output)
        self.assertIn("required headings are out of order", output)

    def test_the_project_name_comes_from_the_title(self) -> None:
        """Renaming the title without the two derived headings breaks both."""
        code, output = self.rewrite(self.text.replace('<h1 align="center">AgtMLS</h1>', '<h1 align="center">Other</h1>'))
        self.assertEqual(code, 1, output)
        self.assertIn("missing heading: The Other ecosystem", output)
        self.assertIn("missing heading: When not to use Other", output)

    def test_missing_structure_is_named(self) -> None:
        code, output = self.rewrite(self.text.replace("ossf-scorecard", "scorecard"))
        self.assertEqual(code, 1, output)
        self.assertIn("missing structure: ossf-scorecard", output)

    def test_a_missing_readme_is_refused(self) -> None:
        self.readme.unlink()
        code, output = self.drive()
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: README.md is missing", output)
