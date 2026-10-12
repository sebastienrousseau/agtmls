# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Unit tests for context optimizer module."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _lib.context_optimizer import (
    enforce_cache_friendly_prefix,
    estimate_tokens,
    instruction_density,
    pack_repomix_xml,
    prune_boilerplate,
)


class TestContextOptimizer(unittest.TestCase):
    def test_prune_boilerplate(self) -> None:
        raw = (
            "Please make sure to check the code.\n\n\n\n"
            "It is important to run tests.\n"
            "Always remember to sign commits.\n"
            "As an AI coding assistant, I write clean code.\n"
            "In order to pass, run the gate."
        )
        pruned = prune_boilerplate(raw)
        self.assertNotIn("Please make sure to", pruned)
        self.assertNotIn("It is important to", pruned)
        self.assertNotIn("Always remember to", pruned)
        self.assertNotIn("As an AI coding assistant,", pruned)
        self.assertNotIn("In order to", pruned)
        self.assertNotIn("\n\n\n", pruned)
        self.assertEqual(prune_boilerplate("Please make sure to\n"), "\n")

    def test_estimate_tokens(self) -> None:
        self.assertEqual(estimate_tokens(""), 0)
        self.assertGreaterEqual(estimate_tokens("Hello world"), 1)
        self.assertEqual(estimate_tokens("a" * 38), 10)

    def test_instruction_density(self) -> None:
        self.assertEqual(instruction_density(""), 0.0)
        sample = (
            "- rule one\n"
            "* rule two\n"
            "1. rule three\n"
            "| col1 | col2 |\n"
        )
        density = instruction_density(sample)
        self.assertGreater(density, 0.0)

    def test_enforce_cache_friendly_prefix(self) -> None:
        lines = ["# Invariants", "Generated at 2026-10-12T22:00:00Z", "Rule A"]
        text = "\n".join(lines)
        res = enforce_cache_friendly_prefix(text)
        self.assertNotIn("2026-10-12T22:00:00", res)
        self.assertIn("Rule A", res)

        # Timestamps beyond line 50 should be preserved
        long_lines = [f"Line {i}" for i in range(55)]
        long_lines[52] = "Log at 2026-10-12T22:00:00Z"
        res_long = enforce_cache_friendly_prefix("\n".join(long_lines))
        self.assertIn("2026-10-12T22:00:00Z", res_long)

    def test_pack_repomix_xml(self) -> None:
        items = [
            ("file1.md", "# Title 1\nContent 1"),
            ("file2.md", "# Title 2\nContent 2"),
        ]
        xml = pack_repomix_xml(items)
        self.assertIn('<context_pack version="1.0" generator="agtmls">', xml)
        self.assertIn('<file path="file1.md"', xml)
        self.assertIn('<file path="file2.md"', xml)
        self.assertIn("</context_pack>", xml)

        # Test truncation when exceeding max_tokens
        truncated_xml = pack_repomix_xml(items, max_tokens=5)
        self.assertIn("Truncated:", truncated_xml)
        self.assertNotIn('<file path="file2.md"', truncated_xml)


if __name__ == "__main__":
    unittest.main()
