# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""validate-check-manifest.py, against a tree built to break it.

test_gate.py asserts the real repository agrees with itself. That proves the
check passes; it cannot prove the check would notice anything. Each case here
builds a minimal tree that is correct, breaks exactly one of the agreements
the check exists to hold, and requires the matching refusal -- with the clean
tree passing first, so a refusal means something.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar

from .support import load_script, retarget, run_main

RUNNER_SOURCE = (
    "import json\n"
    "MANIFEST = 'checks.json'\n"
    "def manifest_checks():\n"
    "    return json.load(open(MANIFEST))['checks']\n"
)


class CheckManifestValidatorTests(unittest.TestCase):
    """Manifest, runner, workflow and prose must describe one gate."""

    # Ten checks: enough that a tree with one removed is still a valid gate.
    CHECKS: ClassVar[list[str]] = ["alpha.py", "beta.py --strict", *(f"c{i}.py" for i in range(8))]

    def setUp(self) -> None:
        self.mod = load_script("validate-check-manifest.py")
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        retarget(self.mod, self.root)
        self.write("checks.json", json.dumps({"schema_version": 1, "checks": self.CHECKS}))
        self.write("scripts/run-all-checks.py", RUNNER_SOURCE)
        for check in self.CHECKS:
            self.write(f"scripts/{check.split()[0]}", "raise SystemExit(0)\n")
        self.write(".github/workflows/validate.yml", "steps:\n" + "".join(
            f"  - run: python3 scripts/{check}\n" for check in self.CHECKS
        ))
        for relative in self.mod.COUNTED:
            self.write(relative, "Run the 10-check gate before pushing.\n")

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def failures(self) -> tuple[int, list[str], str]:
        code, out = run_main(self.mod)
        return code, [line for line in out.splitlines() if line.startswith("FAIL: ")], out

    def test_a_consistent_tree_passes(self) -> None:
        code, failures, out = self.failures()
        self.assertEqual((code, failures), (0, []), out)
        self.assertIn("OK: check manifest valid with 10 check(s), all present in CI", out)

    def test_an_unknown_schema_is_refused(self) -> None:
        self.write("checks.json", json.dumps({"schema_version": 2, "checks": self.CHECKS}))
        code, failures, _ = self.failures()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: checks.json schema_version must be 1", failures)
        self.assertEqual(failures[-1], "FAIL: 1 check manifest issue(s)")

    def test_a_runner_that_keeps_its_own_list_is_refused(self) -> None:
        """A second copy of the gate is where the drift began: the compile
        list had lost four scripts, one of them the security analyzer."""
        self.write(
            "scripts/run-all-checks.py",
            RUNNER_SOURCE + "CHECKS = ['alpha.py']\nCOMPILE = CHECKS\n",
        )
        _, failures, _ = self.failures()
        self.assertIn("FAIL: run-all-checks.py re-declares the gate as CHECKS; "
                      "it must read checks.json", failures)
        self.assertIn("FAIL: run-all-checks.py re-declares the gate as COMPILE; "
                      "it must read checks.json", failures)

    def test_a_runner_that_never_reads_the_manifest_is_refused(self) -> None:
        self.write("scripts/run-all-checks.py", "print('hello')\n")
        code, failures, _ = self.failures()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: run-all-checks.py never reads checks.json", failures)

    def test_a_stale_count_in_prose_is_refused_with_its_location(self) -> None:
        """Criterion 5.9: a count nobody enforces drifts, and a report that
        does not say where would be ignored."""
        self.write("README.md", "intro\n\nThe repository has 57 validation gates.\n")
        _, failures, _ = self.failures()
        self.assertIn("FAIL: README.md:3: claims 57 checks; checks.json has 10", failures)

    def test_a_marked_historical_count_is_left_alone(self) -> None:
        self.write("CONTRIBUTING.md", "It was a 57-check gate. check-count:historical\n")
        code, failures, out = self.failures()
        self.assertEqual((code, failures), (0, []), out)

    def test_a_counted_document_that_disappears_is_refused(self) -> None:
        """Deleting the file must not be a way to satisfy the count."""
        (self.root / "docs" / "ECOSYSTEM.md").unlink()
        _, failures, _ = self.failures()
        self.assertIn("FAIL: counted document missing: docs/ECOSYSTEM.md", failures)

    def test_a_manifest_entry_without_its_script_is_refused(self) -> None:
        (self.root / "scripts" / "beta.py").unlink()
        _, failures, _ = self.failures()
        self.assertIn("FAIL: manifest check script missing: beta.py", failures)

    def test_a_check_ci_does_not_run_is_refused(self) -> None:
        """A local-only check makes CI weaker than `agtmls check`, which is
        how three checks once passed locally and never ran on a pull request."""
        workflow = self.root / ".github" / "workflows" / "validate.yml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8").replace("scripts/beta.py", "scripts/gamma.py"),
            encoding="utf-8",
        )
        _, failures, _ = self.failures()
        self.assertEqual(failures, [
            "FAIL: check not run by validate.yml: beta.py --strict",
            "FAIL: 1 check manifest issue(s)",
        ])

    def test_a_missing_workflow_is_one_refusal_not_one_per_check(self) -> None:
        (self.root / ".github" / "workflows" / "validate.yml").unlink()
        _, failures, _ = self.failures()
        self.assertEqual(failures, [
            "FAIL: CI workflow missing: .github/workflows/validate.yml",
            "FAIL: 1 check manifest issue(s)",
        ])

    def test_an_annotated_redeclaration_is_refused(self) -> None:
        """`CHECKS: list[str] = [...]` is the same second copy of the gate;
        only plain assignments were looked at."""
        self.write("scripts/run-all-checks.py", RUNNER_SOURCE + "CHECKS: list[str] = ['alpha.py']\n")
        _, failures, _ = self.failures()
        self.assertIn(
            "FAIL: run-all-checks.py re-declares the gate as CHECKS; it must read checks.json", failures
        )

    def test_a_check_ci_only_mentions_is_refused(self) -> None:
        """A comment naming the script, or a step running it with different
        arguments, is not CI running that check."""
        workflow = self.root / ".github/workflows/validate.yml"
        text = workflow.read_text(encoding="utf-8")
        text = text.replace("  - run: python3 scripts/beta.py --strict\n", "  # scripts/beta.py --strict runs locally\n")
        text = text.replace("  - run: python3 scripts/c0.py\n", "  - run: python3 scripts/c0.py --lenient\n")
        workflow.write_text(text, encoding="utf-8")
        _, failures, _ = self.failures()
        self.assertIn("FAIL: check not run by validate.yml: beta.py --strict", failures)
        self.assertIn("FAIL: check not run by validate.yml: c0.py", failures)

    def test_a_single_digit_count_is_still_a_claim(self) -> None:
        """The pattern matched only two- and three-digit counts, so a gate of
        fewer than ten checks had every stated count unchecked."""
        self.write("checks.json", json.dumps({"schema_version": 1, "checks": self.CHECKS[:9]}))
        for relative in self.mod.COUNTED:
            self.write(relative, "Run the 8-check gate before pushing.\n")
        _, failures, _ = self.failures()
        self.assertIn("FAIL: AGENTS.md:1: claims 8 checks; checks.json has 9", failures)

    def test_every_problem_is_reported_in_one_pass(self) -> None:
        self.write("checks.json", json.dumps({"checks": self.CHECKS}))
        self.write("Makefile", "all: 99-check gate\n")
        (self.root / "scripts" / "alpha.py").unlink()
        _, failures, _ = self.failures()
        self.assertEqual(failures[-1], "FAIL: 3 check manifest issue(s)")


class CountClaimTests(unittest.TestCase):
    """The pattern and the exemption, as functions."""

    def setUp(self) -> None:
        self.mod = load_script("validate-check-manifest.py")

    def test_claims_carry_their_line_numbers(self) -> None:
        text = (
            "the 64-check suite\n"
            "nothing here\n"
            "Detailed reference of all 12 CI validation gates, and 64 gates\n"
            "old 57-check gate check-count:historical\n"
            "a 7-check claim counts too, however few the checks\n"
        )
        self.assertEqual(
            self.mod.count_claims(text), [(64, 1), (12, 3), (64, 3), (7, 5)]
        )

    def test_only_module_level_list_names_count_as_redeclarations(self) -> None:
        """A local variable called CHECKS inside a function is not a second
        gate; a module-level one is."""
        with TemporaryDirectory() as raw:
            runner = Path(raw) / "runner.py"
            runner.write_text(
                "def f():\n    CHECKS = []\n"
                "COMPILE = []\nOTHER = []\nCHECKS = x = []\nobj.CHECKS = []\n",
                encoding="utf-8",
            )
            self.assertEqual(self.mod.redeclared_lists(runner), ["CHECKS", "COMPILE"])
