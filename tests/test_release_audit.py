# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""release-audit.py: a published release, read back from each place it lives.

git, gh and PyPI are replaced by a fake that answers like one published
release; each case breaks one location and requires the audit to say which.
Run against the real v0.0.5, the audit refuses it: its notes are the
workflow's one-line default and its PyPI files were uploaded by hand.
"""

from __future__ import annotations

import io
import json
import subprocess
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from .support import load_script, run_main

TAG_OBJECT = "1" * 40
COMMIT = "2" * 40
WHEEL, SDIST = "agtmls-0.0.9-py3-none-any.whl", "agtmls-0.0.9.tar.gz"
SUMS = f"{'a' * 64}  {WHEEL}\n{'b' * 64}  {SDIST}\n{'c' * 64}  agtmls-generic-polyglot.tar.gz\n"
BODY = f"## Summary\n\n- A change people notice.\n\n## Checksums\n\n```\n{SUMS}```\n"


class FakeWorld:
    def __init__(self, **overrides) -> None:
        self.state = {
            "local": TAG_OBJECT, "remote": TAG_OBJECT, "peeled": COMMIT, "expected": COMMIT,
            "release": {"body": BODY, "isDraft": False}, "sums": SUMS,
            "pypi": {"urls": [
                {"filename": WHEEL, "digests": {"sha256": "a" * 64}},
                {"filename": SDIST, "digests": {"sha256": "b" * 64}},
            ]},
        }
        self.state.update(overrides)

    def run(self, *cmd: str) -> subprocess.CompletedProcess:
        s = self.state

        def ok(out: str = "", rc: int = 0, err: str = "") -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(cmd, rc, out, err)

        if cmd[:2] == ("git", "rev-parse"):
            return ok((s["expected"] if cmd[2].endswith("^{commit}") else s["local"]) + "\n")
        if cmd[:2] == ("git", "ls-remote"):
            lines = []
            if s["remote"]:
                lines.append(f"{s['remote']}\trefs/tags/v0.0.9")
            if s["peeled"]:
                lines.append(f"{s['peeled']}\trefs/tags/v0.0.9^{{}}")
            return ok("\n".join(lines) + "\n")
        if cmd[:3] == ("gh", "release", "view"):
            if s["release"] is None:
                return ok(rc=1, err="release not found")
            return ok(json.dumps(s["release"]))
        if cmd[:3] == ("gh", "release", "download"):
            if s["sums"] is None:
                return ok(rc=1, err="no assets match")
            Path(cmd[cmd.index("--dir") + 1], "SHA256SUMS").write_text(s["sums"], encoding="utf-8")
            return ok()
        raise AssertionError(f"unexpected command {cmd}")

    def fetch_json(self, url: str):
        assert url == "https://pypi.org/pypi/agtmls/0.0.9/json", url
        return self.state["pypi"]


class AuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_script("release-audit.py")

    def audit(self, world: FakeWorld | None = None, *extra: str) -> tuple[int, list[str], str]:
        world = world or FakeWorld()
        self.mod.run, self.mod.fetch_json = world.run, world.fetch_json
        code, output = run_main(self.mod, "--tag", "v0.0.9", "--commit", COMMIT[:12], *extra)
        return code, [line for line in output.splitlines() if line.startswith("FAIL: ")], output

    def test_a_release_that_agrees_everywhere_passes(self) -> None:
        code, failures, output = self.audit()
        self.assertEqual((code, failures), (0, []), output)
        self.assertIn("OK: v0.0.9 read back from the tag, the GitHub release and PyPI; all agree", output)

    def test_before_pypi_skips_only_pypi(self) -> None:
        code, _, output = self.audit(FakeWorld(pypi=None), "--before-pypi")
        self.assertEqual(code, 0, output)
        self.assertIn("read back from the tag and the GitHub release; all agree", output)

    def test_a_tag_missing_from_the_remote_is_named(self) -> None:
        _, failures, _ = self.audit(FakeWorld(remote="", peeled=""))
        self.assertIn("FAIL: v0.0.9 is not on the remote", failures)

    def test_a_remote_tag_that_is_not_the_signed_one_is_named(self) -> None:
        """Someone else's tag of the same name, or an unsigned re-creation."""
        _, failures, _ = self.audit(FakeWorld(remote="9" * 40))
        self.assertIn("FAIL: remote v0.0.9 is object 999999999999, not the local signed tag 111111111111", failures)

    def test_a_remote_tag_on_another_commit_is_named(self) -> None:
        _, failures, _ = self.audit(FakeWorld(peeled="3" * 40))
        self.assertIn("FAIL: remote v0.0.9 points at 333333333333, not the release commit 222222222222", failures)

    def test_no_local_tag_is_said_plainly(self) -> None:
        _, failures, _ = self.audit(FakeWorld(local=""))
        self.assertIn("FAIL: remote v0.0.9 is object 111111111111, not the local signed tag (none)", failures)

    def test_a_missing_release_stops_the_release_and_pypi_checks(self) -> None:
        _, failures, _ = self.audit(FakeWorld(release=None))
        self.assertEqual(failures[:2], [
            "FAIL: no GitHub release for v0.0.9: release not found",
            "FAIL: PyPI not checked: there is no SHA256SUMS to check it against",
        ])

    def test_a_draft_or_a_release_without_sums_is_named(self) -> None:
        _, failures, _ = self.audit(FakeWorld(release={"body": BODY, "isDraft": True}, sums=None))
        self.assertIn("FAIL: the v0.0.9 release is still a draft", failures)
        self.assertIn("FAIL: the v0.0.9 release has no SHA256SUMS asset", failures)

    def test_the_workflows_one_line_body_is_refused(self) -> None:
        """What v0.0.1-v0.0.5 shipped with: no summary, no checksums."""
        body = "Automated AgtMLS v0.0.9 release. Versions increment by exactly 0.0.1 on the 0.0.x line."
        _, failures, _ = self.audit(FakeWorld(release={"body": body, "isDraft": False}))
        self.assertIn("FAIL: v0.0.9 release body: needs a `## Summary` section of user-visible changes, as bullets", failures)
        self.assertIn("FAIL: v0.0.9 release body: needs a `## Checksums` section", failures)

    def test_body_checksums_that_differ_from_the_asset_are_refused(self) -> None:
        _, failures, _ = self.audit(FakeWorld(sums=SUMS.replace("a" * 64, "d" * 64)))
        self.assertIn("FAIL: v0.0.9 release body: Checksums section does not equal SHA256SUMS", failures)

    def test_a_version_missing_from_pypi_is_named(self) -> None:
        _, failures, _ = self.audit(FakeWorld(pypi=None))
        self.assertIn("FAIL: agtmls 0.0.9 is not on PyPI", failures)

    def test_pypi_files_must_be_the_released_ones(self) -> None:
        """PyPI 0.0.3-0.0.5 were uploaded by hand and match no release asset."""
        pypi = {"urls": [{"filename": WHEEL, "digests": {"sha256": "e" * 64}}]}
        _, failures, _ = self.audit(FakeWorld(pypi=pypi))
        self.assertIn(f"FAIL: PyPI 0.0.9 should carry a wheel and an sdist; it has ['{WHEEL}']", failures)
        self.assertIn(f"FAIL: PyPI {WHEEL} has sha256 eeeeeeeeeeee, which SHA256SUMS does not list", failures)

    def test_an_empty_pypi_release_is_named(self) -> None:
        _, failures, _ = self.audit(FakeWorld(pypi={"urls": []}))
        self.assertIn("FAIL: PyPI 0.0.9 should carry a wheel and an sdist; it has nothing", failures)


class FetchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_script("release-audit.py")

    def test_a_page_is_parsed(self) -> None:
        with mock.patch.object(self.mod.urllib.request, "urlopen", return_value=io.BytesIO(b'{"urls": []}')):
            self.assertEqual(self.mod.fetch_json("https://pypi.org/x"), {"urls": []})

    def test_not_found_is_none_and_anything_else_raises(self) -> None:
        def raising(code):
            return mock.patch.object(
                self.mod.urllib.request, "urlopen",
                side_effect=urllib.error.HTTPError("https://pypi.org/x", code, "no", {}, None),
            )

        with raising(404):
            self.assertIsNone(self.mod.fetch_json("https://pypi.org/x"))
        with raising(503), self.assertRaises(urllib.error.HTTPError):
            self.mod.fetch_json("https://pypi.org/x")

    def test_the_real_runner_captures_output(self) -> None:
        result = self.mod.run("git", "rev-parse", "--is-inside-work-tree")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "true"))


if __name__ == "__main__":
    unittest.main()
