# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""generate-checks-doc.py: docs/checks.md lists exactly the gate.

The hand-kept list had drifted to 47 of 66 checks in another order.  check-count:historical
"""

from __future__ import annotations

import json

from .subset_support import SubsetCase


class ChecksDocTests(SubsetCase):
    SCRIPT = "generate-checks-doc.py"
    SUBSET = ("docs/checks.md", "checks.json")

    def setUp(self) -> None:
        self.preserve("docs/checks.md", "checks.json")

    def listed(self) -> list[str]:
        text = self.path("docs/checks.md").read_text(encoding="utf-8")
        return [line.removeprefix("python3 scripts/") for line in text.splitlines()
                if line.startswith("python3 scripts/") and "agtmls.py check" not in line]

    def manifest(self) -> list[str]:
        return json.loads(self.path("checks.json").read_text(encoding="utf-8"))["checks"]

    def test_the_committed_doc_lists_the_manifest_in_order(self) -> None:
        code, output = self.drive("--check")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.listed(), self.manifest())

    def test_a_new_check_makes_the_doc_stale_until_written(self) -> None:
        data = json.loads(self.path("checks.json").read_text(encoding="utf-8"))
        data["checks"].append("validate-something-new.py")
        self.path("checks.json").write_text(json.dumps(data), encoding="utf-8")
        code, output = self.drive("--check")
        self.assertEqual(code, 1)
        self.assertIn("docs/checks.md does not list checks.json", output)
        code, output = self.drive("--write")
        self.assertEqual((code, output.strip()), (0, "wrote docs/checks.md"))
        self.assertEqual(self.listed()[-1], "validate-something-new.py")
        self.assertEqual(self.drive("--check")[0], 0)

    def test_the_authored_prose_survives_a_write(self) -> None:
        doc = self.path("docs/checks.md")
        doc.write_text(doc.read_text(encoding="utf-8") + "\nA closing note.\n", encoding="utf-8")
        self.drive("--write")
        self.assertTrue(doc.read_text(encoding="utf-8").endswith("\nA closing note.\n"))

    def test_a_doc_without_the_block_is_refused(self) -> None:
        self.path("docs/checks.md").write_text("# The check gate\n", encoding="utf-8")
        for mode in ("--check", "--write"):
            code, output = self.drive(mode)
            self.assertEqual(code, 1, output)
            self.assertIn("docs/checks.md has no <!-- generated:checks", output)
        self.assertEqual(self.path("docs/checks.md").read_text(encoding="utf-8"), "# The check gate\n")

    def test_one_mode_is_required(self) -> None:
        self.assertEqual(self.drive()[0], 2)
