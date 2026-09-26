# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""portability: what stops one skill directory working the same in every agent.

Each case is one construct a single agent honours, or a budget the others
enforce, and the message that names it. The Rust cases are the false
positives a plain `!` + backtick match produced on the noyalib skills: a
`!` inside a code span is Rust, not Claude Code's command injection.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import portability  # needs the scripts path first

FRONT = "---\nname: one\ndescription: Use when testing.\n---\n\n"


class ClaudeOnlyTests(unittest.TestCase):
    def test_command_injection_fences_and_variables_are_found_by_line(self) -> None:
        text = "# One\n\nRun !`git status` first.\n\n```!\nls\n```\n\nThen ${CLAUDE_SKILL_DIR}/x and $CLAUDE_PROJECT_DIR.\n"
        self.assertEqual(portability.claude_only(text), [
            (3, "`!`git status`` runs a command only in Claude Code"),
            (5, "a ```! block runs commands only in Claude Code"),
            (9, "`$CLAUDE_PROJECT_DIR` is set only by Claude Code"),
            (9, "`${CLAUDE_SKILL_DIR}` is set only by Claude Code"),
        ])

    def test_rust_and_markdown_that_merely_contain_a_bang_are_not_flagged(self) -> None:
        for text in (
            "`fn invariant_violated(msg) -> !` (`error.rs:1697`)",
            "the `panic!` and `unreachable!` macros",
            "a!`b` is a word then a span",
            "!``not a span``",
            "`a`!`b`",
        ):
            with self.subTest(text=text):
                self.assertEqual(portability.claude_only(text), [])

    def test_the_body_is_what_follows_the_frontmatter(self) -> None:
        self.assertEqual(portability.body(FRONT + "# One\n"), "\n# One\n")
        self.assertEqual(portability.body("# No frontmatter\n"), "# No frontmatter\n")
        self.assertEqual(portability.body("---\nname: one\n"), "")


class ProblemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = Path(tempfile.mkdtemp(prefix="agtmls-portable-")) / "one"
        self.skill.mkdir()
        self.addCleanup(lambda: shutil.rmtree(self.skill.parent, ignore_errors=True))

    def write(self, rel: str, text: str) -> None:
        (self.skill / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.skill / rel).write_text(text, encoding="utf-8")

    def test_a_portable_skill_has_no_problems(self) -> None:
        self.write("SKILL.md", FRONT + "# One\n\nSee [the reference](reference.md) and [code](scripts/run.sh).\n")
        self.write("reference.md", "# Reference\n\nBack to [the skill](SKILL.md), or [the web](https://example.com/a.md).\n")
        self.assertEqual(portability.problems(self.skill), [])

    def test_an_oversized_body_is_named_with_its_estimate(self) -> None:
        self.write("SKILL.md", FRONT + "# One\n" + "x" * 20_100)
        self.assertEqual(portability.problems(self.skill), [
            "SKILL.md body is about 5026 tokens; keep it under 5000 and move detail into a reference file",
        ])

    def test_a_reference_chain_and_claude_only_text_in_a_reference_are_named(self) -> None:
        self.write("SKILL.md", FRONT + "# One\n\nSee [a](docs/a.md).\n")
        self.write("docs/a.md", "# A\n\nThen read [b](b.md). Run !`make`.\n")
        self.write("docs/b.md", "# B\n")
        self.assertEqual(portability.problems(self.skill), [
            "docs/a.md:3: `!`make`` runs a command only in Claude Code",
            "docs/a.md links to docs/b.md: keep references one level deep from SKILL.md",
        ])

    def test_a_link_leaving_the_skill_is_not_a_reference_chain(self) -> None:
        self.write("SKILL.md", FRONT + "# One\n")
        self.write("reference.md", "See [the other skill](../two/reference.md).\n")
        self.assertEqual(portability.problems(self.skill), [])


class SummaryTests(unittest.TestCase):
    def test_repeats_are_grouped_by_rule_with_a_count_and_examples(self) -> None:
        messages = [
            "SKILL.md body is about 6000 tokens; keep it under 5000 and move detail into a reference file",
            "SKILL.md:19: `${CLAUDE_SKILL_DIR}` is set only by Claude Code",
            "SKILL.md:81: `${CLAUDE_SKILL_DIR}` is set only by Claude Code",
            "ref/a.md:3: `${CLAUDE_SKILL_DIR}` is set only by Claude Code",
            "ref/b.md:9: `${CLAUDE_SKILL_DIR}` is set only by Claude Code",
            *[f"ref/{n}.md links to ref/x.md: keep references one level deep from SKILL.md" for n in "abcd"],
        ]
        self.assertEqual(portability.summarize(messages), [
            messages[0],
            "`${CLAUDE_SKILL_DIR}` is set only by Claude Code: 4 place(s), e.g. SKILL.md:19, SKILL.md:81, ref/a.md:3",
            (
                "4 reference link(s) go more than one level deep from SKILL.md, "
                "e.g. ref/a.md -> ref/x.md, ref/b.md -> ref/x.md, ref/c.md -> ref/x.md"
            ),
        ])
        single = ["SKILL.md:8: `!`make`` runs a command only in Claude Code",
                  "ref/a.md links to ref/b.md: keep references one level deep from SKILL.md"]
        self.assertEqual(portability.summarize(single), single)

    def test_one_line_repeating_a_construct_is_one_problem(self) -> None:
        skill = Path(tempfile.mkdtemp(prefix="agtmls-portable-")) / "one"
        skill.mkdir()
        self.addCleanup(lambda: shutil.rmtree(skill.parent, ignore_errors=True))
        (skill / "SKILL.md").write_text(FRONT + "# One\n\n${CLAUDE_SKILL_DIR}/a ${CLAUDE_SKILL_DIR}/b\n", encoding="utf-8")
        self.assertEqual(portability.problems(skill), ["SKILL.md:8: `${CLAUDE_SKILL_DIR}` is set only by Claude Code"])


if __name__ == "__main__":
    unittest.main()
