# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The committed SBOMs and provenance must survive a squash merge.

They were stamped from `git log`: the date of the newest commit touching the
described paths, and provenance also named that commit's hash. A squash merge
replaces the branch's commits with one new commit, new date and new hash, on
the same tree -- so the artifacts regenerated on the branch were stale the
moment they reached main, and main's CI failed after every squash merge
(d229411, c4eba07) while every pull request check had passed.

The same tree must get the same verdict whatever history it sits in.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from unittest import mock

from .subset_support import SubsetCase

GENERATED = ("SBOM.spdx.json", "SBOM.cyclonedx.json", "provenance.json")


class SquashMergeTests(SubsetCase):
    """A real repository, a real squash: the incident, reproduced."""

    SUBSET = (
        ".claude-plugin", "templates", "LICENSE-MIT",
        "index.json", "checks.json", "mcp-resources.json", *GENERATED,
    )

    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("SOURCE_DATE_EPOCH", None)
        self.preserve(*GENERATED)

    def git(self, *args: str, date: str = "2026-01-01T00:00:00+00:00") -> str:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date,
        }
        return subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
            cwd=self.fixture, env=env, text=True, capture_output=True, check=True,
        ).stdout.strip()

    def regenerate(self, flag: str) -> list[tuple[int, str]]:
        return [self.drive(flag, module=self.script(name))
                for name in ("generate-sbom.py", "generate-provenance.py")]

    def test_a_squash_merge_leaves_the_artifacts_current(self) -> None:
        self.git("init", "-q")
        self.addCleanup(shutil.rmtree, self.fixture / ".git", ignore_errors=True)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "branch: source change")
        for code, output in self.regenerate("--write"):
            self.assertEqual(code, 0, output)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "branch: regenerate", date="2026-01-01T00:05:00+00:00")
        for code, output in self.regenerate("--check"):
            self.assertEqual(code, 0, f"stale on the branch itself:\n{output}")

        # What GitHub's squash merge does: one new commit, same tree, new date.
        tree = self.git("rev-parse", "HEAD^{tree}")
        squash = self.git("commit-tree", tree, "-m", "squash", date="2026-01-02T09:00:00+00:00")
        self.git("update-ref", "HEAD", squash)
        self.assertEqual(self.git("status", "--porcelain"), "")

        for code, output in self.regenerate("--check"):
            self.assertEqual(code, 0, f"a squash merge made a current artifact stale:\n{output}")


class StampTests(SubsetCase):
    """The stamp moves when the described content does, and only then."""

    SCRIPT = "generate-sbom.py"
    SUBSET = (".claude-plugin", "templates", "LICENSE-MIT", "SBOM.spdx.json", "SBOM.cyclonedx.json")

    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.preserve("SBOM.spdx.json", "SBOM.cyclonedx.json", "templates")

    def stamps(self) -> tuple[str, str]:
        spdx = json.loads(self.path("SBOM.spdx.json").read_text(encoding="utf-8"))
        bom = json.loads(self.path("SBOM.cyclonedx.json").read_text(encoding="utf-8"))
        return spdx["creationInfo"]["created"], bom["metadata"]["timestamp"]

    def test_unchanged_content_keeps_its_stamp(self) -> None:
        os.environ["SOURCE_DATE_EPOCH"] = "86400"
        self.drive("--write")
        self.assertEqual(self.stamps(), ("1970-01-02T00:00:00Z",) * 2)
        os.environ["SOURCE_DATE_EPOCH"] = "172800"
        self.drive("--write")
        self.assertEqual(self.stamps(), ("1970-01-02T00:00:00Z",) * 2, "an unchanged SBOM was re-stamped")
        self.assertEqual(self.drive("--check")[0], 0)

    def test_changed_content_takes_a_new_stamp(self) -> None:
        os.environ["SOURCE_DATE_EPOCH"] = "86400"
        self.drive("--write")
        self.path("templates/NEW.md").write_text("new\n", encoding="utf-8")
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        os.environ["SOURCE_DATE_EPOCH"] = "172800"
        self.drive("--write")
        self.assertEqual(self.stamps(), ("1970-01-03T00:00:00Z",) * 2)
        self.assertEqual(self.drive("--check")[0], 0)

    def test_without_a_pinned_clock_the_stamp_is_now_in_utc(self) -> None:
        os.environ.pop("SOURCE_DATE_EPOCH", None)
        self.path("SBOM.spdx.json").unlink()
        self.path("SBOM.cyclonedx.json").unlink()
        module = self.script()
        with mock.patch.object(module.stamp, "clock", return_value=1_800_000_000):
            self.drive("--write", module=module)
        self.assertEqual(self.stamps(), ("2027-01-15T08:00:00Z",) * 2)

    def test_a_missing_or_malformed_stamp_is_stale(self) -> None:
        os.environ["SOURCE_DATE_EPOCH"] = "86400"
        self.drive("--write")
        path = self.path("SBOM.spdx.json")
        spdx = json.loads(path.read_text(encoding="utf-8"))
        for bad in ("2026-01-02T03:04:05+01:00", "", None):
            with self.subTest(stamp=bad):
                spdx["creationInfo"]["created"] = bad
                path.write_text(json.dumps(spdx, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                code, output = self.drive("--check")
                self.assertEqual(code, 1, output)
                self.assertIn("SBOM.spdx.json", output)
        del spdx["creationInfo"]
        path.write_text(json.dumps(spdx), encoding="utf-8")
        self.assertEqual(self.drive("--check")[0], 1)
        path.write_text("not json", encoding="utf-8")
        self.assertEqual(self.drive("--check")[0], 1)
