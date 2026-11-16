# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""_lib/frontmatter: the one reader of `---` blocks, used by nine scripts."""

from __future__ import annotations

import sys
import unittest

from .support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))

from _lib import frontmatter


class FrontmatterTests(unittest.TestCase):
    def test_split_returns_the_block_and_the_body(self) -> None:
        self.assertEqual(frontmatter.split("---\nname: x\n---\n# Body\n"), ("name: x", "# Body\n"))
        self.assertEqual(frontmatter.split("--- \nname: x\n---\t\nrest"), ("name: x", "rest"))

    def test_no_block_is_none(self) -> None:
        for text in ("# no frontmatter\n", "---\nname: x\n", "---\r\nname: x\r\n---\r\n"):
            with self.subTest(text=text):
                self.assertIsNone(frontmatter.split(text))
                self.assertIsNone(frontmatter.fields(text, " "))
                self.assertIsNone(frontmatter.line_value(text, "name"))

    def test_continuation_lines_join_with_the_callers_joiner(self) -> None:
        text = "---\ndescription: >\n  one\n  two\nname: x\n---\n"
        self.assertEqual(frontmatter.fields(text, " "), {"description": "one two", "name": "x"})
        self.assertEqual(frontmatter.fields(text, "\n")["description"], "one\ntwo")

    def test_quotes_are_left_to_the_caller(self) -> None:
        self.assertEqual(frontmatter.fields('---\nname: "q"\n---\n', " "), {"name": '"q"'})

    def test_lines_before_the_first_key_and_indented_keys_belong_to_no_field(self) -> None:
        text = "---\n  stray\nname: x\n  nested: y\n---\n"
        self.assertEqual(frontmatter.fields(text, " "), {"name": "x nested: y"})

    def test_a_later_duplicate_key_wins(self) -> None:
        self.assertEqual(frontmatter.fields("---\nname: a\nname: b\n---\n", " "), {"name": "b"})

    def test_line_value_is_the_raw_first_line(self) -> None:
        text = '---\nallowed-tools: "Read Bash"  \nlicense:\n---\n'
        self.assertEqual(frontmatter.line_value(text, "allowed-tools"), '"Read Bash"  ')
        self.assertEqual(frontmatter.line_value(text, "license"), "")
        self.assertIsNone(frontmatter.line_value(text, "name"))


if __name__ == "__main__":
    unittest.main()
