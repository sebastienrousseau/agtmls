# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""release-body.py: the GitHub release page, from the notes and the build.

The notes hold only the hand-written Highlights; the PR list comes from
GitHub's generate-notes and the checksums from the build. This joins them in
the Release Page Format, and the result must pass the audit's own rules. A
release with no prepared notes fails instead of shipping the workflow's
one-line default.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from .support import load_script, run_main

SUMS = f"{'a' * 64}  agtmls-0.0.9-py3-none-any.whl\n{'b' * 64}  agtmls-0.0.9.tar.gz\n"
HIGHLIGHTS = "* **A change**: people notice it.\n* **Another change**: also noticed.\n"
NOTES = (
    "<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->\n\n# AgtMLS v0.0.9\n\n"
    f"## Highlights ⭐️\n\n{HIGHLIGHTS}\n## Checksums\n\nPending CI build.\n"
)
COMPARE = "**Full Changelog**: https://github.com/o/r/compare/v0.0.8...v0.0.9"
CHANGE = "* feat: a change by @someone in https://github.com/o/r/pull/7"
GENERATED = f"<!-- Release notes generated using configuration -->\n## What's Changed\n{CHANGE}\n\n\n{COMPARE}"
COMMITS = [
    {"html_url": "https://github.com/o/r/commit/1", "author": {"login": "someone"},
     "commit": {"message": "feat: first\n\nbody", "author": {"name": "Some One"}}},
    {"html_url": "https://github.com/o/r/commit/2", "author": None,
     "commit": {"message": "fix: second", "author": {"name": "nobody"}}},
]


class ReleaseBodyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_script("release-body.py")
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-body-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        (self.tmp / "notes").mkdir()
        (self.tmp / "notes" / "v0.0.9.md").write_text(NOTES, encoding="utf-8")
        (self.tmp / "SHA256SUMS").write_text(SUMS, encoding="utf-8")
        (self.tmp / "generated.md").write_text(GENERATED, encoding="utf-8")
        (self.tmp / "commits.json").write_text(json.dumps(COMMITS), encoding="utf-8")
        self.out = self.tmp / "body.md"

    def build(self, tag: str = "v0.0.9", *extra: str) -> tuple[int, str]:
        return run_main(
            self.mod, "--tag", tag, "--notes-dir", str(self.tmp / "notes"),
            "--sums", str(self.tmp / "SHA256SUMS"), "--generated", str(self.tmp / "generated.md"),
            "--out", str(self.out), *extra,
        )

    def test_the_page_is_composed_in_the_release_page_format(self) -> None:
        code, output = self.build()
        self.assertEqual(code, 0, output)
        self.assertEqual(
            self.out.read_text(encoding="utf-8"),
            f"## Highlights ⭐️\n\n{HIGHLIGHTS.rstrip()}\n\n## What's Changed\n\n{CHANGE}\n\n"
            f"## Checksums\n\n```\n{SUMS}```\n\n{COMPARE}\n",
        )

    def test_the_result_passes_the_audits_rules(self) -> None:
        self.build()
        rules = load_script("release-audit.py")
        body = self.out.read_text(encoding="utf-8")
        self.assertEqual(rules.notes_problems("body", body, SUMS, published=True), [])

    def test_new_contributors_are_kept_before_the_checksums(self) -> None:
        contributors = "* @newcomer made their first contribution in https://github.com/o/r/pull/7"
        (self.tmp / "generated.md").write_text(
            f"## What's Changed\n{CHANGE}\n\n## New Contributors\n{contributors}\n\n{COMPARE}\n", encoding="utf-8"
        )
        self.build()
        body = self.out.read_text(encoding="utf-8")
        self.assertIn(f"{CHANGE}\n\n## New Contributors\n\n{contributors}\n\n## Checksums", body)
        rules = load_script("release-audit.py")
        self.assertEqual(rules.notes_problems("body", body, SUMS, published=True), [])

    def test_a_range_without_pull_requests_lists_its_commits(self) -> None:
        (self.tmp / "generated.md").write_text(f"\n\n{COMPARE}\n", encoding="utf-8")
        code, output = self.build("v0.0.9", "--commits", str(self.tmp / "commits.json"))
        self.assertEqual(code, 0, output)
        body = self.out.read_text(encoding="utf-8")
        self.assertIn(
            "## What's Changed\n\n* feat: first by @someone in https://github.com/o/r/commit/1\n"
            "* fix: second by @nobody in https://github.com/o/r/commit/2\n\n", body,
        )

    def test_a_range_without_pull_requests_or_commits_fails(self) -> None:
        (self.tmp / "generated.md").write_text(f"{COMPARE}\n", encoding="utf-8")
        code, output = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: the generated notes have no `## What's Changed` and no --commits were given", output)
        self.assertFalse(self.out.exists())

    def test_generated_notes_without_a_full_changelog_fail(self) -> None:
        (self.tmp / "generated.md").write_text(f"## What's Changed\n{CHANGE}\n", encoding="utf-8")
        code, output = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: the generated notes have no `**Full Changelog**` line", output)

    def test_notes_without_highlights_fail(self) -> None:
        (self.tmp / "notes" / "v0.0.9.md").write_text("# v\n\n## Summary\n\n- A change.\n", encoding="utf-8")
        code, output = self.build()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: v0.0.9.md: needs a `## Highlights ⭐️` section of user-visible changes", output)
        self.assertFalse(self.out.exists())

    def test_a_release_without_prepared_notes_fails(self) -> None:
        code, output = self.build(tag="v0.0.8")
        self.assertEqual(code, 1)
        self.assertIn(f"FAIL: no release notes at {self.tmp / 'notes' / 'v0.0.8.md'}", output)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
