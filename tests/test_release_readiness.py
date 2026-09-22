# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Two release questions that are answered by reading, not by building.

Can each release workflow publish -- does it mint an OIDC token, name its
environment, rehearse, pin its actions? And what changed between two indexes?
Both are run by hand before a release, so neither had evidence it answers
correctly. A readiness check that reports "ok" for a workflow missing
`id-token: write` defers the failure to the publish step, where it reads like
a bad token.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import load_script, retarget, run_main

PINNED = "actions/checkout@" + "a" * 40

#: A release workflow that satisfies every repository-side requirement.
READY = f"""\
on:
  workflow_dispatch:
    inputs:
      dry_run: {{type: boolean}}
permissions:
  id-token: write
jobs:
  publish:
    environment: pypi
    steps:
      - uses: {PINNED}
      - run: test "$TAG" = "v$VERSION" || echo "tag does not match version"
"""


class PublishingReadinessCheckTests(unittest.TestCase):
    """Each requirement, removed on its own, must be named on its own."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_script("check-publishing-readiness.py")
        cls.base = Path(tempfile.mkdtemp(prefix="agtmls-ready-")).resolve()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.base, ignore_errors=True)

    def repo(self, workflow: str) -> Path:
        repo = Path(tempfile.mkdtemp(dir=self.base))
        (repo / ".github" / "workflows").mkdir(parents=True)
        (repo / ".github" / "workflows" / "release.yml").write_text(workflow, encoding="utf-8")
        return repo

    def problems(self, workflow: str) -> list[str]:
        return self.mod.check("agtmls", self.repo(workflow), "PyPI", "pypi")

    def test_a_ready_workflow_has_no_problems(self) -> None:
        self.assertEqual(self.problems(READY), [])

    def test_a_workflow_that_cannot_mint_a_token_is_named(self) -> None:
        self.assertEqual(self.problems(READY.replace("id-token: write", "contents: read")),
                         ["workflow does not declare `id-token: write`; OIDC will fail at publish"])

    def test_a_workflow_in_the_wrong_environment_is_named(self) -> None:
        self.assertEqual(self.problems(READY.replace("environment: pypi", "environment: prod")),
                         ["workflow does not use `environment: pypi`"])

    def test_a_workflow_that_cannot_rehearse_is_named(self) -> None:
        self.assertEqual(self.problems(READY.replace("dry_run", "publish_now")),
                         ["no dry_run input; there is no way to rehearse"])

    def test_a_workflow_that_never_compares_tag_and_version_is_named(self) -> None:
        workflow = READY.replace('      - run: test "$TAG" = "v$VERSION" || echo "tag does not match version"\n', "")
        self.assertEqual(self.problems(workflow),
                         ["workflow does not appear to check the tag against the version"])

    def test_an_action_pinned_to_a_tag_is_named_with_the_first_offender(self) -> None:
        workflow = READY.replace(PINNED, "actions/checkout@v4") + "      - uses: actions/setup-python@v5\n"
        self.assertEqual(self.problems(workflow),
                         ["2 action(s) not pinned to a SHA: - uses: actions/checkout@v4"])

    def test_a_local_action_without_a_ref_is_not_an_unpinned_one(self) -> None:
        self.assertEqual(self.problems(READY + "      - uses: ./.github/actions/setup\n"), [])

    def test_the_report_lists_every_package_and_fails_on_any_problem(self) -> None:
        ready = self.repo(READY)
        broken = self.repo(READY.replace("id-token: write", ""))
        packages = [
            ("agtmls", ready, "PyPI", "pypi"),
            ("@agtmls/wasm", broken, "npmjs", "pypi"),
            ("ghost", self.base / "absent", "crates.io", "crates-io"),
        ]
        with mock.patch.object(self.mod, "PACKAGES", packages):
            code, output = run_main(self.mod)
        self.assertEqual(code, 1)
        self.assertIn("ok    agtmls", output)
        self.assertIn("FAIL  @agtmls/wasm", output)
        self.assertIn(f"repository not found at {self.base / 'absent'}", output)
        self.assertIn("[ ] crates.io  trusted publisher for ghost, environment crates-io", output)
        self.assertIn("FAIL: 2 repository-side issue(s)", output)

    def test_the_report_passes_when_every_workflow_is_ready(self) -> None:
        packages = [("agtmls", self.repo(READY), "PyPI", "pypi")]
        with mock.patch.object(self.mod, "PACKAGES", packages):
            code, output = run_main(self.mod)
        self.assertEqual(code, 0, output)
        self.assertIn("OK: every release workflow is ready; the registry side is manual", output)


def index(**skills: dict) -> dict:
    return {"skills": [{"name": name, **fields} for name, fields in skills.items()]}


class RegistryDiffTests(unittest.TestCase):
    """What a release changes, as the reviewer of a release PR needs to see it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.base = Path(tempfile.mkdtemp(prefix="agtmls-diff-")).resolve()
        cls.mod = load_script("registry-diff.py")
        retarget(cls.mod, cls.base)
        cls.old = cls.base / "old.json"
        cls.new = cls.base / "new.json"
        cls.old.write_text(json.dumps(index(
            kept={"digest": "a"}, edited={"digest": "b"}, dropped={"digest": "c"},
        )), encoding="utf-8")
        cls.new.write_text(json.dumps(index(
            kept={"digest": "a"}, edited={"digest": "B"}, fresh={"digest": "d"}, alpha={},
        )), encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.base, ignore_errors=True)

    def test_added_removed_and_changed_are_reported_sorted(self) -> None:
        code, output = run_main(self.mod, "--from", str(self.old), "--to", str(self.new))
        self.assertEqual(code, 0, output)
        self.assertEqual(output, (
            "added: 2\n  + alpha\n  + fresh\n"
            "removed: 1\n  - dropped\n"
            "changed: 1\n  * edited\n"
        ))

    def test_json_output_carries_the_same_three_lists(self) -> None:
        code, output = run_main(self.mod, "--from", str(self.old), "--to", str(self.new), "--json")
        self.assertEqual(code, 0, output)
        self.assertEqual(json.loads(output),
                         {"added": ["alpha", "fresh"], "removed": ["dropped"], "changed": ["edited"]})

    def test_an_index_compared_with_itself_has_no_changes(self) -> None:
        code, output = run_main(self.mod, "--from", str(self.old), "--to", str(self.old))
        self.assertEqual((code, output), (0, "added: 0\nremoved: 0\nchanged: 0\n"))

    def test_a_revision_spec_is_read_through_git_show(self) -> None:
        shown = subprocess.CompletedProcess([], 0, json.dumps(index(dropped={})), "")
        with mock.patch.object(self.mod.subprocess, "run", return_value=shown) as run:
            data = self.mod.load("v0.0.5:index.json")
        self.assertEqual(data, index(dropped={}))
        self.assertEqual(run.call_args.args[0], ["git", "show", "v0.0.5:index.json"])
        self.assertEqual(run.call_args.kwargs["cwd"], self.base)

    def test_an_unreadable_revision_reports_what_git_said(self) -> None:
        for stderr, expected in (
            ("fatal: invalid object name 'v9'.\n", "fatal: invalid object name 'v9'."),
            ("", "cannot read v9:index.json"),
        ):
            failed = subprocess.CompletedProcess([], 128, "", stderr)
            with mock.patch.object(self.mod.subprocess, "run", return_value=failed), \
                    self.assertRaises(SystemExit) as caught:
                self.mod.load("v9:index.json")
            self.assertEqual(str(caught.exception), expected)

    def test_a_missing_file_that_is_not_a_revision_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            self.mod.load(str(self.base / "nowhere.json"))
        self.assertEqual(str(caught.exception), f"index not found: {self.base / 'nowhere.json'}")
