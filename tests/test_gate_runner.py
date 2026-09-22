# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The gate's runner, driven in-process with nothing real spawned.

run-all-checks.py is the one script every other check depends on for its
verdict to reach anybody. The cases in test_gate.py run real child processes
to prove scheduling holds; these replace the children with recorded fakes so
the orchestration itself -- the command it builds, the order it reports in,
what it writes and where, and the exit code it derives -- is observed line by
line without paying for, or recursing into, the gate.
"""

from __future__ import annotations

import json
import threading
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from .support import load_script, retarget, run_main


def fake_clock(*readings: float):
    """perf_counter that returns exactly these readings, in order."""
    return mock.Mock(side_effect=list(readings))


class RunOneTests(unittest.TestCase):
    """One check becomes one interpreter invocation, and its cost is kept."""

    def setUp(self) -> None:
        self.mod = load_script("run-all-checks.py")

    def test_the_command_is_the_interpreter_the_script_and_its_arguments(self) -> None:
        """A manifest entry carries arguments; losing or re-splitting them
        would run a different check than the one the manifest names."""
        calls = []

        def run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return types.SimpleNamespace(returncode=3, stdout="said something\n")

        fake = types.SimpleNamespace(run=run, PIPE=-1, STDOUT=-2)
        with mock.patch.object(self.mod, "subprocess", fake), \
                mock.patch.object(self.mod.time, "perf_counter", fake_clock(10.0, 12.5)):
            result = self.mod.run_one("audit.py --all 'two words'", Path("/scripts"))

        (cmd, kwargs), = calls
        self.assertEqual(
            cmd, [self.mod.sys.executable, "/scripts/audit.py", "--all", "two words"]
        )
        self.assertEqual(kwargs["cwd"], self.mod.ROOT)
        # stderr folded into stdout: a check that explains itself on stderr
        # would otherwise report a failure with no reason attached.
        self.assertEqual(kwargs["stderr"], fake.STDOUT)
        self.assertEqual(result.check, "audit.py --all 'two words'")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.duration_s, 2.5)
        self.assertEqual(result.output, "said something\n")


class DefaultJobsTests(unittest.TestCase):
    """The pool is sized to the machine, within bounds."""

    def test_the_pool_is_bounded_on_both_sides(self) -> None:
        """Unknown CPU count must still run; a 64-core runner must not spawn
        64 interpreters that each import the registry at once."""
        mod = load_script("run-all-checks.py")
        for cpus, expected in ((None, 1), (1, 1), (4, 4), (8, 8), (64, 8)):
            with mock.patch.object(mod.os, "cpu_count", return_value=cpus):
                self.assertEqual(mod.default_jobs(), expected, f"cpu_count={cpus}")


class RunChecksSchedulingTests(unittest.TestCase):
    """Scheduling decisions, observed without a single child process."""

    def setUp(self) -> None:
        self.mod = load_script("run-all-checks.py")
        self.log: list[tuple[str, str]] = []
        self.lock = threading.Lock()

    def fake_run_one(self, returncodes: dict[str, int] | None = None):
        returncodes = returncodes or {}

        def run_one(check, scripts_dir):
            with self.lock:
                self.log.append((check, threading.current_thread().name))
            return self.mod.CheckResult(check, returncodes.get(check, 0), 0.0, f"out {check}")

        return run_one

    def test_results_come_back_in_manifest_order_including_duplicates(self) -> None:
        """Keyed by name, a check listed twice would collapse to one result
        and the gate would under-report itself."""
        checks = ["b.py", "alone.py", "a.py", "b.py"]
        with mock.patch.object(self.mod, "run_one", self.fake_run_one({"a.py": 1})), \
                mock.patch.object(self.mod, "EXCLUSIVE", frozenset({"alone.py"})):
            results = self.mod.run_checks(checks, jobs=2, scripts_dir=Path("/x"))
        self.assertEqual([r.check for r in results], checks)
        self.assertEqual([r.returncode for r in results], [0, 0, 1, 0])
        self.assertEqual(len(self.log), 4, "every entry must run, duplicates included")

    def test_exclusive_checks_run_after_the_pool_and_outside_it(self) -> None:
        """A tree-mutating check that ran on a pool thread, or before the pool
        drained, could be observed half-done by a concurrent reader."""
        checks = ["alone.py --flag", "one.py", "two.py", "three.py"]
        with mock.patch.object(self.mod, "run_one", self.fake_run_one()), \
                mock.patch.object(self.mod, "EXCLUSIVE", frozenset({"alone.py"})):
            self.mod.run_checks(checks, jobs=3, scripts_dir=Path("/x"))
        self.assertEqual(self.log[-1][0], "alone.py --flag", "the exclusive check ran early")
        self.assertEqual(self.log[-1][1], threading.current_thread().name)
        for check, thread in self.log[:-1]:
            self.assertNotEqual(thread, threading.current_thread().name, check)

    def test_a_gate_of_only_exclusive_checks_opens_no_pool(self) -> None:
        pool = mock.Mock(side_effect=AssertionError("a pool was opened for nothing"))
        with mock.patch.object(self.mod, "run_one", self.fake_run_one()), \
                mock.patch.object(self.mod, "ThreadPoolExecutor", pool), \
                mock.patch.object(self.mod, "EXCLUSIVE", frozenset({"alone.py"})):
            results = self.mod.run_checks(["alone.py"], jobs=4, scripts_dir=Path("/x"))
        self.assertEqual([r.check for r in results], ["alone.py"])

    def test_no_jobs_means_the_machine_default(self) -> None:
        """--jobs 0 or an omitted value must not reach ThreadPoolExecutor,
        which rejects zero workers."""
        seen = []
        real = self.mod.ThreadPoolExecutor

        def pool(max_workers):
            seen.append(max_workers)
            return real(max_workers=max_workers)

        with mock.patch.object(self.mod, "run_one", self.fake_run_one()), \
                mock.patch.object(self.mod, "default_jobs", return_value=5), \
                mock.patch.object(self.mod, "ThreadPoolExecutor", pool):
            self.mod.run_checks(["a.py"], jobs=None, scripts_dir=Path("/x"))
            self.mod.run_checks(["a.py"], jobs=0, scripts_dir=Path("/x"))
            self.mod.run_checks(["a.py"], jobs=2, scripts_dir=Path("/x"))
        self.assertEqual(seen, [5, 5, 2])


def result(mod, check: str, returncode: int = 0, duration: float = 1.0, output: str = ""):
    return mod.CheckResult(check, returncode, duration, output)


class RecordTests(unittest.TestCase):
    """Every run leaves a record, and the records do not grow forever."""

    def setUp(self) -> None:
        self.mod = load_script("run-all-checks.py")
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        retarget(self.mod, Path(self._tmp.name).resolve())

    def test_the_record_states_what_ran_what_failed_and_what_it_cost(self) -> None:
        results = [
            result(self.mod, "a.py", 0, 1.25),
            result(self.mod, "b.py --strict", 2, 0.5),
        ]
        path = self.mod.record(results, 1.4999, jobs=3)
        self.assertEqual(path.parent, self.mod.RUNS_DIR)
        self.assertRegex(path.name, r"^gate-\d{4}-\d{2}-\d{2}T\d{6}Z\.json$")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["jobs"], 3)
        self.assertEqual(payload["wall_s"], 1.5)
        self.assertEqual(payload["cpu_s"], 1.75)
        self.assertEqual(payload["checks"], 2)
        self.assertEqual(payload["failed"], ["b.py --strict"])
        self.assertEqual(payload["durations"], {"a.py": 1.25, "b.py --strict": 0.5})

    def test_only_the_newest_records_are_retained(self) -> None:
        """Names sort chronologically, so the oldest are the ones dropped --
        and the one just written must never be among them."""
        runs = self.mod.RUNS_DIR
        runs.mkdir(parents=True)
        for day in range(1, self.mod.RETAINED_RUNS + 6):
            (runs / f"gate-2000-01-{day:02d}T000000Z.json").write_text("{}", encoding="utf-8")
        (runs / "bench-1999-01-01T000000Z.json").write_text("{}", encoding="utf-8")

        newest = self.mod.record([result(self.mod, "a.py")], 1.0, jobs=1)

        kept = sorted(p.name for p in runs.glob("gate-*.json"))
        self.assertEqual(len(kept), self.mod.RETAINED_RUNS)
        self.assertIn(newest.name, kept)
        self.assertNotIn("gate-2000-01-01T000000Z.json", kept)
        self.assertNotIn("gate-2000-01-06T000000Z.json", kept)
        self.assertIn("gate-2000-01-07T000000Z.json", kept)
        self.assertTrue((runs / "bench-1999-01-01T000000Z.json").exists(),
                        "pruning the gate's history must not touch other records")


class ReportTests(unittest.TestCase):
    """What a person reads after the gate, the only part most people see."""

    def setUp(self) -> None:
        self.mod = load_script("run-all-checks.py")

    def render(self, results, wall=2.0, jobs=4) -> str:
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.mod.report(results, wall, jobs)
        return buffer.getvalue()

    def test_every_failure_is_shown_with_its_own_output(self) -> None:
        results = [
            result(self.mod, "ok.py", 0, 0.1, "fine\n"),
            result(self.mod, "bad-a.py", 1, 0.2, "first defect\n\n"),
            result(self.mod, "bad-b.py", 7, 0.3, "second defect"),
        ]
        text = self.render(results)
        self.assertIn("=== FAIL (1) bad-a.py ===\nfirst defect\n", text)
        self.assertIn("=== FAIL (7) bad-b.py ===\nsecond defect\n", text)
        self.assertNotIn("fine", text, "a passing check's chatter buries the failures")
        self.assertIn("FAIL: 2 of 3 check(s) failed:\n  - bad-a.py\n  - bad-b.py\n", text)
        self.assertNotIn("OK:", text)

    def test_the_five_slowest_are_listed_slowest_first(self) -> None:
        results = [result(self.mod, f"c{i}.py", 0, float(i)) for i in range(7)]
        text = self.render(results, wall=5.0, jobs=2)
        listed = [line.split()[-1] for line in text.splitlines() if line.startswith("  ")]
        self.assertEqual(listed, ["c6.py", "c5.py", "c4.py", "c3.py", "c2.py"])
        self.assertIn("7 check(s) in 5.00s wall (21.00s serial, 2 job(s))", text)
        self.assertIn("OK: 7 check(s) passed", text)


class RunnerMainTests(unittest.TestCase):
    """The entry point: manifest in, verdict and records out."""

    def setUp(self) -> None:
        self.mod = load_script("run-all-checks.py")
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        retarget(self.mod, self.root)
        (self.root / "checks.json").write_text(
            json.dumps({"schema_version": 1, "checks": ["a.py", "b.py --x"]}), encoding="utf-8"
        )
        self.seen: dict[str, object] = {}

    def drive(self, *args: str, returncodes=(0, 0)) -> tuple[int, str]:
        def run_checks(checks, jobs=None):
            self.seen["checks"], self.seen["jobs"] = checks, jobs
            return [
                result(self.mod, check, code, duration, f"output of {check}")
                for check, code, duration in zip(checks, returncodes, (0.25, 1.5))
            ]

        with mock.patch.object(self.mod, "run_checks", run_checks), \
                mock.patch.object(self.mod.time, "perf_counter", fake_clock(100.0, 103.0)):
            return run_main(self.mod, *args)

    def test_a_clean_gate_exits_zero_and_records_the_run(self) -> None:
        code, out = self.drive("--jobs", "3")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.seen, {"checks": ["a.py", "b.py --x"], "jobs": 3})
        self.assertIn("2 check(s) in 3.00s wall (1.75s serial, 3 job(s))", out)
        self.assertEqual(len(list((self.root / ".agtmls" / "runs").glob("gate-*.json"))), 1)
        self.assertFalse(self.mod.RECORD.exists(), "only --record may write the committed file")

    def test_one_failing_check_fails_the_gate(self) -> None:
        code, out = self.drive(returncodes=(0, 1))
        self.assertEqual(code, 1)
        self.assertIn("=== FAIL (1) b.py --x ===\noutput of b.py --x", out)

    def test_json_output_is_the_run_record_and_nothing_else(self) -> None:
        """A machine reader parses the whole of stdout; one stray line of
        prose and the format flag is a lie."""
        code, out = self.drive("--format", "json", returncodes=(2, 0))
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertRegex(payload["run"], r"^\.agtmls/runs/gate-.*\.json$")
        self.assertTrue((self.root / payload["run"]).exists())
        self.assertEqual(
            [(r["check"], r["returncode"]) for r in payload["results"]],
            [("a.py", 2), ("b.py --x", 0)],
        )

    def test_record_writes_the_committed_measurement_and_says_if_it_failed(self) -> None:
        """A duration from a failed run is not "the gate passes in N seconds"."""
        code, out = self.drive("--record", "--jobs", "2", returncodes=(0, 4))
        self.assertEqual(code, 1)
        self.assertIn("recorded benchmarks/results/gate.json", out)
        recorded = json.loads(self.mod.RECORD.read_text(encoding="utf-8"))
        self.assertIs(recorded["passed"], False)
        self.assertEqual(recorded["failed"], ["b.py --x"])
        self.assertEqual(recorded["jobs"], 2)
        self.assertEqual(recorded["checks"], 2)
        self.assertEqual(recorded["wall_s"], 3.0)
        self.assertEqual(recorded["serial_s"], 1.75)
        # A mapping, and written with sorted keys, so rank is in the values.
        self.assertEqual(recorded["slowest"], {"b.py --x": 1.5, "a.py": 0.25})
        self.assertEqual(recorded["generated_by"], "scripts/run-all-checks.py --record")

        code, _ = self.drive("--record")
        self.assertEqual(code, 0)
        self.assertIs(json.loads(self.mod.RECORD.read_text(encoding="utf-8"))["passed"], True)


class UnitRunnerTests(unittest.TestCase):
    """run-unit-tests.py, with discovery and the runner replaced.

    Letting it discover for real would run this suite from inside itself.
    What matters is the verdict it derives from a result: a failed run and a
    run that found nothing must both fail, because an empty green suite is
    the failure the runner exists to prevent.
    """

    def drive(self, *, successful: bool, tests_run: int) -> tuple[int, str, dict]:
        mod = load_script("run-unit-tests.py")
        seen: dict[str, object] = {}
        with TemporaryDirectory() as raw:
            fixture = Path(raw).resolve()
            retarget(mod, fixture)

            def discover(start_dir, top_level_dir):
                seen["start_dir"], seen["top_level_dir"] = start_dir, top_level_dir
                seen["path_head"] = mod.sys.path[0]
                return "the suite"

            class Runner:
                def __init__(self, verbosity):
                    seen["verbosity"] = verbosity

                def run(self, suite):
                    seen["ran"] = suite
                    return types.SimpleNamespace(
                        wasSuccessful=lambda: successful, testsRun=tests_run
                    )

            fake = types.SimpleNamespace(
                defaultTestLoader=types.SimpleNamespace(discover=discover),
                TextTestRunner=Runner,
            )
            with mock.patch.object(mod, "unittest", fake), \
                    mock.patch.object(mod.sys, "path", list(mod.sys.path)):
                code, out = run_main(mod)
            seen["fixture"] = fixture
        return code, out, seen

    def test_discovery_is_rooted_at_the_repository(self) -> None:
        code, out, seen = self.drive(successful=True, tests_run=3)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "OK: 3 unit test(s) passed")
        self.assertEqual(seen["start_dir"], str(seen["fixture"] / "tests"))
        self.assertEqual(seen["top_level_dir"], str(seen["fixture"]))
        self.assertEqual(seen["path_head"], str(seen["fixture"]))
        self.assertEqual(seen["ran"], "the suite")

    def test_a_failing_suite_fails(self) -> None:
        code, out, _ = self.drive(successful=False, tests_run=3)
        self.assertEqual(code, 1)
        self.assertNotIn("OK:", out)

    def test_a_suite_that_found_nothing_fails(self) -> None:
        """unittest calls zero tests a success. A discovery that silently
        stopped matching would turn the whole suite green."""
        code, out, _ = self.drive(successful=True, tests_run=0)
        self.assertEqual(code, 1)
        self.assertIn("FAIL: discovery found no tests", out)
