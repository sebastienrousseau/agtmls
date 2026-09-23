# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The gate: its manifest, its scheduling, and the analyzer it runs."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from .support import (  # noqa: F401  (used by the cases below)
    CLI,
    ROOT,
    load_script,
    skill_text,
)


class CheckManifestTests(unittest.TestCase):
    """checks.json is the gate. CI must run all of it, and the local runner
    must read it rather than keep a copy."""

    def manifest(self) -> list[str]:
        return json.loads((ROOT / "checks.json").read_text(encoding="utf-8"))["checks"]

    def test_manifest_is_covered_by_ci(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        for check in self.manifest():
            self.assertIn(f"scripts/{check.split()[0]}", workflow, f"{check} is not run by CI")

    def test_runner_keeps_no_second_copy_of_the_gate(self) -> None:
        """A hardcoded list in the runner is how the gate drifts.

        The compile list that used to live here had already lost four
        scripts, one of them the security analyzer, while reading as
        exhaustive.
        """
        tree = ast.parse((ROOT / "scripts" / "run-all-checks.py").read_text(encoding="utf-8"))
        duplicated = sorted(
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name) and target.id in {"CHECKS", "COMPILE"}
        )
        self.assertEqual(
            duplicated, [], f"run-all-checks.py re-declares the gate as {duplicated}"
        )

    def test_runner_reads_the_manifest(self) -> None:
        module = load_script("run-all-checks.py")
        self.assertEqual(module.manifest_checks(), self.manifest())

    def test_runner_reports_every_failure(self) -> None:
        """Returning on the first failure costs one CI round trip per fix."""
        module = load_script("run-all-checks.py")
        with tempfile.TemporaryDirectory() as raw:
            scripts = Path(raw)
            (scripts / "passes.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
            (scripts / "fails-a.py").write_text(
                "print('first defect'); raise SystemExit(1)\n", encoding="utf-8"
            )
            (scripts / "fails-b.py").write_text(
                "print('second defect'); raise SystemExit(1)\n", encoding="utf-8"
            )
            results = module.run_checks(
                ["passes.py", "fails-a.py", "fails-b.py"], jobs=3, scripts_dir=scripts
            )
        self.assertEqual(len(results), 3)
        failed = sorted(r.check for r in results if r.returncode != 0)
        self.assertEqual(failed, ["fails-a.py", "fails-b.py"])
        joined = "".join(r.output for r in results)
        self.assertIn("first defect", joined)
        self.assertIn("second defect", joined)

    def test_an_exclusive_check_never_overlaps_another(self) -> None:
        """Tree-mutating checks must not share the pool.

        smoke-make-install.py runs `make install`, whose prerequisites
        regenerate completions/ and share/man/ inside the working tree. A
        concurrent reader of those files is a flaky gate, so the guarantee is
        asserted here rather than assumed.
        """
        module = load_script("run-all-checks.py")
        with tempfile.TemporaryDirectory() as raw:
            scripts = Path(raw)
            log = scripts / "windows.txt"
            # Raw: the \n below belongs to the generated script, not to this
            # file. time.time(), not perf_counter(), because these windows are
            # compared across processes.
            probe = textwrap.dedent(
                r"""
                import sys, time
                name, path = sys.argv[1], sys.argv[2]
                start = time.time()
                time.sleep(0.05)
                with open(path, "a") as handle:
                    handle.write("%s %r %r\n" % (name, start, time.time()))
                """
            )
            names = ["alone.py", "one.py", "two.py", "three.py"]
            for name in names:
                (scripts / name).write_text(
                    f"import sys\nsys.argv = [sys.argv[0], {name!r}, {str(log)!r}]\n"
                    + probe,
                    encoding="utf-8",
                )
            original = module.EXCLUSIVE
            module.EXCLUSIVE = frozenset({"alone.py"})
            try:
                results = module.run_checks(names, jobs=4, scripts_dir=scripts)
            finally:
                module.EXCLUSIVE = original
            # Without this the probes could fail silently and the overlap
            # assertions below would pass over an empty log.
            for result in results:
                self.assertEqual(result.returncode, 0, f"{result.check}: {result.output}")

            windows = {}
            for line in log.read_text(encoding="utf-8").splitlines():
                name, start, end = line.split()
                windows[name] = (float(start), float(end))

        self.assertEqual(sorted(windows), sorted(names))
        alone_start, alone_end = windows["alone.py"]
        for name in ["one.py", "two.py", "three.py"]:
            start, end = windows[name]
            self.assertFalse(
                start < alone_end and alone_start < end,
                f"{name} ran while the exclusive check did",
            )

    def test_documented_check_count_matches_the_manifest(self) -> None:
        """Criterion 5.9: a README claim nobody enforces is a README claim that drifts.

        The count read 57 in AGENTS.md and 62 in the Makefile while the
        manifest held 62, and fixing those left four more "57-gate" claims  check-count:historical
        in README.md that a search for the other spellings did not find.
        """
        module = load_script("validate-check-manifest.py")
        total = len(self.manifest())
        self.assertGreater(len(module.COUNTED), 0)
        for relative in module.COUNTED:
            path = ROOT / relative
            self.assertTrue(path.exists(), f"{relative} is counted but missing")
            # count_claims(), not the raw pattern: a test that reimplements the
            # scan is a test of the reimplementation.
            for claimed, line in module.count_claims(path.read_text(encoding="utf-8")):
                self.assertEqual(claimed, total, f"{relative}:{line} claims {claimed}")

    def test_the_count_pattern_actually_matches_prose(self) -> None:
        """A regex that matches nothing would make the check above vacuous."""
        module = load_script("validate-check-manifest.py")
        total = len(self.manifest())
        for shape in [
            "Run the full {n}-check validation suite",
            "The repository has {n} validation gates and tests.",
            "Detailed reference of all {n} CI validation gates.",
            "Gate: **{n} checks**, all green",
            "make targets, {n}-gate validation suite",
        ]:
            text = shape.format(n=total)
            self.assertEqual(
                [claimed for claimed, _ in module.count_claims(text)], [total],
                f"pattern missed: {text!r}",
            )
        # And the exemption has to actually exempt, or historical prose
        # becomes unwriteable.
        fixture = f"it was a 57-check gate {module.HISTORICAL}"  # check-count:historical
        self.assertEqual(module.count_claims(fixture), [])

    def test_tree_mutating_checks_are_declared_exclusive(self) -> None:
        """Both known tree-mutating checks must stay out of the pool.

        smoke-install-verify.py writes to skills/writing-plans/SKILL.md and
        smoke-make-install.py regenerates completions/ and share/man/. A
        concurrent reader of either is a flaky gate. The full list was derived
        by running each check alone and watching every file's mtime; re-run
        that scan when a check starts writing something.
        """
        module = load_script("run-all-checks.py")
        for name in ("smoke-install-verify.py", "smoke-make-install.py"):
            self.assertIn(name, module.EXCLUSIVE, f"{name} would race the pool")

    def test_the_tamper_test_still_restores_what_it_tampered(self) -> None:
        """If the restore ever stops happening, the repository is corrupted.

        This is why that check is scheduled alone rather than rewritten: the
        tampering is the point of the test.
        """
        source = (ROOT / "scripts" / "smoke-install-verify.py").read_text(encoding="utf-8")
        self.assertIn('drifted.write_text(backup + "\\ndrifted\\n", encoding="utf-8")', source)
        self.assertIn("finally:", source)
        self.assertIn('drifted.write_text(backup, encoding="utf-8")', source)

    def test_every_exclusive_check_is_in_the_manifest(self) -> None:
        """The isolation list annotates manifest entries; it cannot outlive one."""
        module = load_script("run-all-checks.py")
        scripts = {check.split()[0] for check in self.manifest()}
        for name in module.EXCLUSIVE:
            self.assertIn(name, scripts, f"{name} is isolated but is not a gate check")


class RegistryAuditGateTests(unittest.TestCase):
    """The analyzer must be pointed at the skills this repository ships.

    run-security-evals.py proves the analyzer *can* detect things by replaying
    a corpus. It says nothing about skills/, which is what users install.
    """

    def test_registry_audit_runs_in_the_gate(self) -> None:
        checks = json.loads((ROOT / "checks.json").read_text(encoding="utf-8"))["checks"]
        self.assertIn("audit-skill.py --all --strict", checks)

    def test_registry_audit_rejects_a_tampered_skill(self) -> None:
        """A gate check that cannot fail is not a check.

        The payload comes from the security corpus rather than a literal here:
        one copy of every attack string, and scripts/ stays clean.
        """
        corpus = json.loads(
            (ROOT / "evals" / "security" / "corpus.json").read_text(encoding="utf-8")
        )
        case = next(c for c in corpus["cases"] if c["name"] == "split-line-injection")
        with tempfile.TemporaryDirectory() as raw:
            skill = Path(raw) / "tampered"
            skill.mkdir()
            for name, body in case["files"].items():
                (skill / name).write_text(body, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "audit-skill.py"), str(skill), "--strict"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(proc.returncode, 0, "the analyzer passed a known injection")
        self.assertIn("AGT-INJ", proc.stdout)
