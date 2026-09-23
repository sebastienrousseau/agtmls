# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""release-body.py: the GitHub release body, from the notes and the build.

The notes are written before the tag; the checksums exist only after the
workflow builds. This joins them: the prepared notes, with their Checksums
section replaced by the SHA256SUMS the workflow just wrote. A release with no
prepared notes fails instead of shipping the workflow's one-line default.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from .support import load_script, run_main

SUMS = f"{'a' * 64}  agtmls-0.0.9-py3-none-any.whl\n{'b' * 64}  agtmls-0.0.9.tar.gz\n"
NOTES = (
    "<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->\n\n# AgtMLS v0.0.9\n\n"
    "## Summary\n\n- A change.\n\n## Checksums\n\nPending CI build.\n\n## Thanks\n\nEveryone.\n"
)


class ReleaseBodyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_script("release-body.py")
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-body-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        (self.tmp / "notes").mkdir()
        (self.tmp / "notes" / "v0.0.9.md").write_text(NOTES, encoding="utf-8")
        (self.tmp / "SHA256SUMS").write_text(SUMS, encoding="utf-8")
        self.out = self.tmp / "body.md"

    def build(self, tag: str = "v0.0.9") -> tuple[int, str]:
        return run_main(
            self.mod, "--tag", tag, "--notes-dir", str(self.tmp / "notes"),
            "--sums", str(self.tmp / "SHA256SUMS"), "--out", str(self.out),
        )

    def test_the_pending_checksums_become_the_real_ones(self) -> None:
        code, output = self.build()
        self.assertEqual(code, 0, output)
        body = self.out.read_text(encoding="utf-8")
        self.assertIn(f"## Checksums\n\n```\n{SUMS}```\n", body)
        self.assertNotIn("Pending", body)
        self.assertIn("## Thanks\n\nEveryone.\n", body, "the sections after Checksums were lost")
        self.assertNotIn("SPDX", body, "the licence comment is repository metadata, not release notes")

    def test_the_result_passes_the_audits_notes_rules(self) -> None:
        self.build()
        rules = load_script("release-audit.py")
        self.assertEqual(rules.notes_problems("body", self.out.read_text(encoding="utf-8"), SUMS), [])

    def test_notes_without_a_checksums_section_get_one(self) -> None:
        (self.tmp / "notes" / "v0.0.9.md").write_text("# v\n\n## Summary\n\n- A change.\n", encoding="utf-8")
        self.build()
        self.assertTrue(self.out.read_text(encoding="utf-8").endswith(f"## Checksums\n\n```\n{SUMS}```\n"))

    def test_a_release_without_prepared_notes_fails(self) -> None:
        code, output = self.build(tag="v0.0.8")
        self.assertEqual(code, 1)
        self.assertIn(f"FAIL: no release notes at {self.tmp / 'notes' / 'v0.0.8.md'}", output)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
