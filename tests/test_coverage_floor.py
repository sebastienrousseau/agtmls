# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""run-coverage.py: the floor that may rise and must never fall.

Every subprocess it would start is replaced by a recorder. Running coverage
for real from inside the suite would measure the suite measuring itself, cost
minutes, and -- because the script deletes `.coverage*` in its root -- destroy
the measurement of whoever is running these tests under coverage. The fixture
root is a temporary directory, so `coverage-floor.json` in the repository is
never read or written here.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from .support import load_script, retarget, run_main


class FakeSubprocess:
    """Stands in for the `subprocess` module the script imported.

    Replacing the module attribute rather than patching subprocess.run keeps
    the substitution local to the script under test.
    """

    PIPE = subprocess.PIPE
    STDOUT = subprocess.STDOUT
    DEVNULL = subprocess.DEVNULL

    def __init__(self, *, target_rc: int = 0, target_out: str = "", report_out: str = ""):
        self.calls: list[tuple[list[str], dict]] = []
        self.target_rc = target_rc
        self.target_out = target_out
        self.report_out = report_out
        self.hook_source = None

    def run(self, cmd, **kwargs):
        self.calls.append((list(cmd), kwargs))
        if cmd[1] == "run":
            # The hook directory is temporary; read it while it exists.
            first = kwargs["env"]["PYTHONPATH"].split(os.pathsep)[0]
            self.hook_source = (Path(first) / "sitecustomize.py").read_text(encoding="utf-8")
            return types.SimpleNamespace(returncode=self.target_rc, stdout=self.target_out)
        if cmd[1] == "report":
            return types.SimpleNamespace(returncode=0, stdout=self.report_out)
        return types.SimpleNamespace(returncode=0, stdout="")


REPORT = (
    "Name                 Stmts   Miss  Cover\n"
    "scripts/_lib/x.py       10      1    90%\n"
    "TOTAL                   10      1  87.25%\n"
)


class CoverageToolTests(unittest.TestCase):
    """Finding coverage is the first thing that can go wrong, and the error
    has to say how to fix it rather than dump a traceback."""

    def setUp(self) -> None:
        self.mod = load_script("run-coverage.py")

    def test_an_executable_on_path_is_used_as_is(self) -> None:
        probe = mock.Mock(side_effect=AssertionError("probed despite a PATH hit"))
        with mock.patch.object(self.mod.shutil, "which", return_value="/bin/coverage"), \
                mock.patch.object(self.mod, "subprocess", types.SimpleNamespace(run=probe)):
            self.assertEqual(self.mod.coverage_cmd(), ["/bin/coverage"])

    def test_an_importable_module_is_run_through_this_interpreter(self) -> None:
        """pip install --user leaves the module importable and no script on PATH."""
        probe = mock.Mock(return_value=types.SimpleNamespace(returncode=0))
        with mock.patch.object(self.mod.shutil, "which", return_value=None), \
                mock.patch.object(self.mod, "subprocess", types.SimpleNamespace(run=probe)):
            self.assertEqual(
                self.mod.coverage_cmd(), [self.mod.sys.executable, "-m", "coverage"]
            )
        self.assertEqual(probe.call_args.args[0][1:], ["-c", "import coverage"])

    def test_absence_is_a_refusal_that_says_what_to_install(self) -> None:
        probe = mock.Mock(return_value=types.SimpleNamespace(returncode=1))
        with mock.patch.object(self.mod.shutil, "which", return_value=None), \
                mock.patch.object(self.mod, "subprocess", types.SimpleNamespace(run=probe)), \
                self.assertRaises(SystemExit) as raised:
            self.mod.coverage_cmd()
        self.assertIn("coverage is not installed", str(raised.exception.code))
        self.assertIn("pip install coverage", str(raised.exception.code))


class MeasureTests(unittest.TestCase):
    """measure(): which suite runs, how children are traced, what is read back."""

    def setUp(self) -> None:
        self.mod = load_script("run-coverage.py")
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        retarget(self.mod, self.root)
        patcher = mock.patch.object(self.mod, "coverage_cmd", return_value=["cov"])
        patcher.start()
        self.addCleanup(patcher.stop)

    def measure(self, scope: str, fake: FakeSubprocess, pythonpath: str | None = None):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        if pythonpath is not None:
            env["PYTHONPATH"] = pythonpath
        self.out = io.StringIO()
        with mock.patch.object(self.mod, "subprocess", fake), \
                mock.patch.dict(self.mod.os.environ, env, clear=True), \
                contextlib.redirect_stdout(self.out):
            return self.mod.measure(scope)

    def test_core_runs_the_unit_suite_and_reports_only_the_library(self) -> None:
        """core is the library measured from tests, not from incidental
        execution; widening the report would make it a different number."""
        fake = FakeSubprocess(report_out=REPORT)
        self.assertEqual(self.measure("core", fake), 87.25)
        self.assertIn("TOTAL", self.out.getvalue(), "the table is the evidence; it must be shown")
        (run, run_kw), (combine, _), (report, _) = fake.calls
        self.assertEqual(run, ["cov", "run", str(self.root / "scripts" / "run-unit-tests.py")])
        self.assertEqual(combine, ["cov", "combine", "-q"])
        self.assertEqual(report, ["cov", "report", "--include", "scripts/_lib/*,src/agtmls/*"])
        self.assertEqual(run_kw["cwd"], self.root)

    def test_all_runs_the_whole_gate_and_reports_everything(self) -> None:
        fake = FakeSubprocess(report_out=REPORT)
        self.measure("all", fake)
        self.assertEqual(fake.calls[0][0][-1], str(self.root / "scripts" / "run-all-checks.py"))
        self.assertEqual(fake.calls[-1][0], ["cov", "report"])

    def test_unit_runs_the_unit_suite_and_reports_everything(self) -> None:
        """The project rule: unit-test coverage of every script, not only the
        library, stays at or above 98%. Widening core would change what the
        100% floor means, so this is its own scope."""
        fake = FakeSubprocess(report_out=REPORT)
        self.assertEqual(self.measure("unit", fake), 87.25)
        self.assertEqual(fake.calls[0][0][-1], str(self.root / "scripts" / "run-unit-tests.py"))
        self.assertEqual(fake.calls[-1][0], ["cov", "report"])

    def test_children_are_traced_without_losing_the_callers_path(self) -> None:
        """Most of the work happens in child processes. Without the hook they
        go unmeasured; overwriting PYTHONPATH would break the ones that need it."""
        fake = FakeSubprocess(report_out=REPORT)
        self.measure("core", fake, pythonpath="/somewhere/else")
        env = fake.calls[0][1]["env"]
        self.assertEqual(env["COVERAGE_PROCESS_START"], str(self.root / "pyproject.toml"))
        parts = env["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[1], "/somewhere/else")
        self.assertIn("coverage.process_startup()", fake.hook_source)

        bare = FakeSubprocess(report_out=REPORT)
        self.measure("core", bare)
        self.assertEqual(len(bare.calls[0][1]["env"]["PYTHONPATH"].split(os.pathsep)), 1)

    def test_stale_data_is_discarded_before_measuring(self) -> None:
        """A leftover .coverage.* from an older run would be combined into
        this one and credit lines nothing here executed."""
        for name in (".coverage", ".coverage.host.123.456"):
            (self.root / name).write_text("stale", encoding="utf-8")
        (self.root / "keep.txt").write_text("mine", encoding="utf-8")
        self.measure("core", FakeSubprocess(report_out=REPORT))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["keep.txt"])

    def test_a_failing_suite_refuses_to_report_a_number(self) -> None:
        """Coverage of a red suite is not a measurement of anything."""
        fake = FakeSubprocess(target_rc=1, target_out="FAILED (failures=2)\n")
        with self.assertRaises(SystemExit) as raised:
            self.measure("all", fake)
        self.assertIn("run-all-checks.py failed under coverage", str(raised.exception.code))
        self.assertIn("FAILED (failures=2)", self.out.getvalue())
        self.assertEqual(len(fake.calls), 1, "nothing may be combined or reported")

    def test_a_report_without_a_total_is_a_refusal_not_zero(self) -> None:
        fake = FakeSubprocess(report_out="No data to report.\n")
        with self.assertRaises(SystemExit) as raised:
            self.measure("core", fake)
        self.assertIn("no TOTAL line", str(raised.exception.code))

    def test_the_last_total_line_wins(self) -> None:
        fake = FakeSubprocess(report_out="TOTAL 1 1 10%\nnoise\nTOTAL 9 1 88.9%\ntrailer\n")
        self.assertEqual(self.measure("core", fake), 88.9)


class FloorTests(unittest.TestCase):
    """main(): the comparison, the tolerance, and the one-way ratchet."""

    def setUp(self) -> None:
        self.mod = load_script("run-coverage.py")
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        retarget(self.mod, Path(self._tmp.name).resolve())
        self.scopes: list[str] = []

    def write_floor(self, floors: dict[str, float], **extra) -> None:
        self.mod.FLOOR.write_text(
            json.dumps({"schema_version": 1, "floors": floors, **extra}), encoding="utf-8"
        )

    def drive(self, measured: float, *args: str) -> tuple[int, str]:
        def measure(scope):
            self.scopes.append(scope)
            return measured

        with mock.patch.object(self.mod, "measure", measure):
            return run_main(self.mod, *args)

    def test_no_floor_file_means_a_floor_of_zero(self) -> None:
        self.assertEqual(self.mod.floors(), {})
        code, out = self.drive(12.0)
        self.assertEqual(code, 0)
        self.assertIn("core: 12.0% against a floor of 0.0%", out)
        self.assertEqual(self.scopes, ["core"])
        self.assertFalse(self.mod.FLOOR.exists(), "a plain run must not write the floor")

    def test_falling_below_the_floor_fails(self) -> None:
        self.write_floor({"core": 80.0})
        code, out = self.drive(79.0)
        self.assertEqual(code, 1)
        self.assertIn("FAIL: core coverage fell below its floor by 1.0 points", out)
        self.assertNotIn("OK:", out)

    def test_rounding_noise_below_the_floor_is_tolerated(self) -> None:
        """The floor is recorded to one decimal; a measurement that rounds to
        it must not fail on the digits that were thrown away."""
        self.write_floor({"core": 80.0})
        code, out = self.drive(79.96)
        self.assertEqual(code, 0, out)
        self.assertIn("OK: core coverage holds at 80.0%", out)
        code, _ = self.drive(79.94)
        self.assertEqual(code, 1)

    def test_a_clear_gain_suggests_raising_the_floor(self) -> None:
        self.write_floor({"all": 50.0})
        code, out = self.drive(50.6, "--scope", "all")
        self.assertEqual(code, 0)
        self.assertEqual(self.scopes, ["all"])
        self.assertIn("the all floor could be raised to 50.6% (run with --update)", out)
        _, quiet = self.drive(50.5, "--scope", "all")
        self.assertNotIn("could be raised", quiet)

    def test_update_refuses_to_lower_the_floor(self) -> None:
        """A floor that moves down is a target, and targets get negotiated."""
        self.write_floor({"core": 80.0})
        before = self.mod.FLOOR.read_bytes()
        code, out = self.drive(79.99, "--update")
        self.assertEqual(code, 1)
        self.assertIn("refusing to lower the core floor from 80.0% to 80.0%", out)
        self.assertEqual(self.mod.FLOOR.read_bytes(), before)

    def test_update_raises_one_scope_and_keeps_the_other(self) -> None:
        self.write_floor({"core": 80.0, "all": 40.0}, extra="kept")
        code, out = self.drive(83.46, "--update")
        self.assertEqual(code, 0)
        self.assertIn("recorded core floor at 83.5%", out)
        written = json.loads(self.mod.FLOOR.read_text(encoding="utf-8"))
        self.assertEqual(written["floors"], {"core": 83.5, "all": 40.0})
        self.assertEqual(written["extra"], "kept")
        self.assertIn("must never fall", written["note"])

    def test_update_creates_the_floor_when_there_is_none(self) -> None:
        code, _ = self.drive(61.04, "--update", "--scope", "all")
        self.assertEqual(code, 0)
        written = json.loads(self.mod.FLOOR.read_text(encoding="utf-8"))
        self.assertEqual(written["schema_version"], 1)
        self.assertEqual(written["floors"], {"all": 61.0})
        self.assertEqual(self.mod.floors(), {"all": 61.0})

    def test_unit_coverage_below_98_fails_even_with_no_floor_recorded(self) -> None:
        """98% is a project rule, not a measurement: it holds before any floor
        is written and after a floor file is edited down."""
        code, out = self.drive(97.9, "--scope", "unit")
        self.assertEqual(code, 1, out)
        self.assertIn("unit: 97.9% against a floor of 98.0%", out)

    def test_a_unit_floor_edited_below_the_rule_does_not_lower_it(self) -> None:
        self.write_floor({"unit": 50.0})
        code, out = self.drive(97.0, "--scope", "unit")
        self.assertEqual(code, 1, out)

    def test_unit_coverage_at_the_rule_passes(self) -> None:
        code, out = self.drive(98.0, "--scope", "unit")
        self.assertEqual(code, 0, out)
