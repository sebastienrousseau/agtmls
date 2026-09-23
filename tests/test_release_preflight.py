# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""release-preflight.py: every reason a tag must not be pushed.

Release tags are protected from deletion, so a wrong one is permanent. Each
case gives the preflight a git that answers like a repository in one wrong
state and requires the refusal that names it; the correct state passes first,
so a refusal means something.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from .support import load_script, run_main

SHA = "a" * 40
DIGEST = "b" * 64
NOTES = (
    "<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->\n\n# AgtMLS v0.0.9\n\n"
    "## Summary\n\n- Something a user will notice.\n\n## Checksums\n\n```\n{sums}```\n"
)


class FakeGit:
    """A repository in a known state; each field is one thing that can be wrong."""

    def __init__(self, **overrides) -> None:
        self.state = {
            "kind": "tag",
            "target": SHA,
            "expected": SHA,
            "subject": "AgtMLS v0.0.9",
            "verify_rc": 0,
            "verify_err": "",
            "pyproject": 'version = "0.0.9"\n',
            "plugin": json.dumps({"version": "0.0.9"}),
            "index": json.dumps({"registry_version": "0.0.9"}),
            "init": '__version__ = "0.0.9"\n',
            "exists": True,
        }
        self.state.update(overrides)
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str) -> subprocess.CompletedProcess:
        self.calls.append(args)
        s = self.state

        def ok(out: str = "", rc: int = 0, err: str = "") -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(args, rc, out, err)

        if args[:2] == ("cat-file", "-t"):
            return ok(s["kind"] + "\n") if s["exists"] else ok(rc=128, err="fatal: not a valid object")
        if args[0] == "rev-parse":
            return ok((s["target"] if args[1].startswith("v") else s["expected"]) + "\n")
        if args[0] == "for-each-ref":
            return ok(s["subject"] + "\n")
        if "verify-tag" in args:
            return ok(rc=s["verify_rc"], err=s["verify_err"])
        if args[0] == "show":
            path = args[1].split(":", 1)[1]
            content = {
                "pyproject.toml": s["pyproject"],
                ".claude-plugin/plugin.json": s["plugin"],
                "index.json": s["index"],
                "src/agtmls/__init__.py": s["init"],
            }[path]
            return ok(content) if content is not None else ok(rc=128, err="fatal: path does not exist")
        raise AssertionError(f"unexpected git call {args}")


class PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_script("release-preflight.py")
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-preflight-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.sums = self.tmp / "SHA256SUMS"
        self.sums.write_text(f"{DIGEST}  agtmls-0.0.9-py3-none-any.whl\n", encoding="utf-8")
        self.notes = self.tmp / "v0.0.9.md"
        self.notes.write_text(NOTES.format(sums=self.sums.read_text(encoding="utf-8")), encoding="utf-8")

    def preflight(self, git: FakeGit | None = None, *extra: str, tag: str = "v0.0.9") -> tuple[int, str]:
        self.mod.git = git or FakeGit()
        args = ["--tag", tag, "--commit", SHA[:12], "--notes", str(self.notes), *extra]
        return run_main(self.mod, *args)

    def failures(self, output: str) -> list[str]:
        return [line for line in output.splitlines() if line.startswith("FAIL: ")]

    def test_a_correct_tag_and_complete_notes_pass(self) -> None:
        code, output = self.preflight(FakeGit(), "--sums", str(self.sums))
        self.assertEqual(code, 0, output)
        self.assertIn("OK: v0.0.9 is a signed, correctly titled tag of 0.0.9 at the intended commit", output)
        self.assertNotIn("WARN", output)

    def test_signatures_are_checked_against_the_published_keys(self) -> None:
        git = FakeGit()
        self.preflight(git, "--sums", str(self.sums))
        verify = next(call for call in git.calls if "verify-tag" in call)
        self.assertEqual(verify[1], f"gpg.ssh.allowedSignersFile={self.mod.KEYS}")

    def test_something_that_is_not_a_release_tag_is_refused_before_git_is_asked(self) -> None:
        git = FakeGit()
        code, output = self.preflight(git, tag="v0.1.0")
        self.assertEqual(code, 1)
        self.assertEqual(self.failures(output), ["FAIL: v0.1.0 is not a release tag of the form v0.0.N"])
        self.assertEqual(git.calls, [])

    def test_a_tag_that_does_not_exist_is_the_only_tag_complaint(self) -> None:
        code, output = self.preflight(FakeGit(exists=False), "--sums", str(self.sums))
        self.assertEqual(code, 1)
        self.assertEqual(self.failures(output)[0],
                         "FAIL: tag v0.0.9 does not exist locally; create it with `git tag -s v0.0.9 <commit>`")
        self.assertIn("FAIL: 1 release preflight issue(s); do not push v0.0.9", output)

    def test_each_wrong_tag_property_is_named(self) -> None:
        cases = {
            "kind": ("commit", "is a lightweight tag; release tags must be annotated and signed (`git tag -s`)"),
            "target": ("c" * 40, "points at cccccccccccc, not the intended release commit aaaaaaaaaaaa"),
            "subject": ("v0.0.9", "message is 'v0.0.9'; it must be exactly 'AgtMLS v0.0.9'"),
            "verify_rc": (1, "is not signed by a key in KEYS.asc: no signature"),
        }
        for field, (value, complaint) in cases.items():
            with self.subTest(field=field):
                code, output = self.preflight(FakeGit(**{field: value}), "--sums", str(self.sums))
                self.assertEqual(code, 1)
                self.assertEqual(self.failures(output)[0], f"FAIL: v0.0.9 {complaint}")

    def test_the_signature_error_git_gives_is_passed_on(self) -> None:
        git = FakeGit(verify_rc=1, verify_err="error: no signature found\n")
        _, output = self.preflight(git, "--sums", str(self.sums))
        self.assertIn("is not signed by a key in KEYS.asc: error: no signature found", output)

    def test_an_intended_commit_that_does_not_exist_is_refused(self) -> None:
        _, output = self.preflight(FakeGit(expected=""), "--sums", str(self.sums))
        self.assertIn(f"FAIL: expected commit {SHA[:12]} does not exist", output)

    def test_every_packaged_version_must_be_the_tags(self) -> None:
        cases = {
            "pyproject": ('version = "0.0.8"\n', "pyproject.toml at the release commit says 0.0.8"),
            "plugin": (json.dumps({"version": "0.0.8"}), ".claude-plugin/plugin.json at the release commit says 0.0.8"),
            "index": (json.dumps({}), "index.json at the release commit says nothing"),
            "init": ("", "src/agtmls/__init__.py at the release commit says nothing"),
        }
        for field, (content, complaint) in cases.items():
            with self.subTest(field=field):
                _, output = self.preflight(FakeGit(**{field: content}), "--sums", str(self.sums))
                self.assertIn(f"FAIL: {complaint}, not 0.0.9", output)

    def test_a_file_the_commit_does_not_have_says_nothing(self) -> None:
        _, output = self.preflight(FakeGit(plugin=None, pyproject=""), "--sums", str(self.sums))
        self.assertIn("FAIL: .claude-plugin/plugin.json at the release commit says nothing, not 0.0.9", output)
        self.assertIn("FAIL: pyproject.toml at the release commit says nothing, not 0.0.9", output)

    def test_notes_without_a_summary_are_refused(self) -> None:
        """A commit list or an empty section is not a summary of what changed."""
        for body in ("## Summary\n\nsee commits\n", "## Changes\n\n- x\n"):
            with self.subTest(body=body):
                self.notes.write_text(f"# v\n\n{body}\n## Checksums\n\npending\n", encoding="utf-8")
                _, output = self.preflight(FakeGit(), "--pending-checksums")
                self.assertIn("needs a `## Summary` section of user-visible changes, as bullets", output)

    def test_notes_without_checksums_are_refused(self) -> None:
        self.notes.write_text("# v\n\n## Summary\n\n- x\n", encoding="utf-8")
        _, output = self.preflight(FakeGit(), "--sums", str(self.sums))
        self.assertIn("FAIL: v0.0.9.md: needs a `## Checksums` section", output)

    def test_checksums_that_differ_from_the_build_are_refused(self) -> None:
        self.sums.write_text(f"{'c' * 64}  agtmls-0.0.9-py3-none-any.whl\n", encoding="utf-8")
        _, output = self.preflight(FakeGit(), "--sums", str(self.sums))
        self.assertIn("FAIL: v0.0.9.md: Checksums section does not equal SHA256SUMS", output)

    def test_a_malformed_sums_file_is_reported(self) -> None:
        self.sums.write_text(self.sums.read_text(encoding="utf-8") + "junk\n", encoding="utf-8")
        _, output = self.preflight(FakeGit(), "--sums", str(self.sums))
        self.assertIn("FAIL: SHA256SUMS line 2 is not '<sha256>  <file>': 'junk'", output)

    def test_checksums_cannot_go_unchecked_without_saying_so(self) -> None:
        _, output = self.preflight(FakeGit())
        self.assertIn("FAIL: v0.0.9.md: no SHA256SUMS to check the Checksums section against", output)

    def test_pending_checksums_pass_with_a_warning_only_if_the_notes_say_so(self) -> None:
        self.notes.write_text("# v\n\n## Summary\n\n- x\n\n## Checksums\n\nPending CI build.\n", encoding="utf-8")
        code, output = self.preflight(FakeGit(), "--pending-checksums")
        self.assertEqual(code, 0, output)
        self.assertIn("WARN: checksums are pending", output)
        self.notes.write_text("# v\n\n## Summary\n\n- x\n\n## Checksums\n\nTBD\n", encoding="utf-8")
        _, output = self.preflight(FakeGit(), "--pending-checksums")
        self.assertIn("pending checksums must be marked `pending` in the Checksums section", output)

    def test_missing_notes_are_refused(self) -> None:
        self.notes.unlink()
        _, output = self.preflight(FakeGit(), "--sums", str(self.sums))
        self.assertIn(f"FAIL: release notes missing: {self.notes}", output)

    def test_the_real_git_wrapper_runs_in_the_repository(self) -> None:
        result = load_script("release-preflight.py").git("rev-parse", "--is-inside-work-tree")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "true"))


if __name__ == "__main__":
    unittest.main()
