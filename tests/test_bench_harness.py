# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""bench.py's harness, with the stopwatch and the workloads replaced.

test_measurement.py covers the arithmetic a baseline is built from. These
cover everything around it -- sampling, calibration, the check's
minimum-of-runs, what gets written and where, and the verdict -- with the
clock and every child process faked. A real run takes minutes and measures
the machine; the questions here are about the code, and a fake clock gives
them exact answers.

The module is retargeted at a temporary root, so bench-baseline.json,
benchmarks/results/ and .agtmls/runs/ in the repository are never touched.
"""

from __future__ import annotations

import contextlib
import io
import json
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from .support import load_script, retarget, run_main


def entry(ratio: float, p50: float = 10.0, min_ms: float = 9.0) -> dict:
    return {
        "warmup": 1, "iterations": 2, "min_ms": min_ms, "p50_ms": p50,
        "p95_ms": p50 + 1.0, "mean_ms": p50, "ratio_to_calibration": ratio,
    }


def suite_report(stamp: str = "2026-01-01T00:00:00Z", **workloads: dict) -> dict:
    return {
        "generated_at": stamp,
        "environment": {"platform": "TestOS-1", "python": "3.12.0"},
        "workloads": {"calibration": entry(1.0), **workloads},
    }


class SamplingTests(unittest.TestCase):
    """run_once and measure: what one sample is, and what a set of them says."""

    def setUp(self) -> None:
        self.mod = load_script("bench.py")

    def test_one_sample_is_timed_and_its_output_kept(self) -> None:
        """The one line that explains a failure is usually on stdout, and
        undecodable bytes in it must not crash the harness that reports it."""
        seen = {}

        def run(argv, **kwargs):
            seen["argv"], seen["kwargs"] = argv, kwargs
            return types.SimpleNamespace(returncode=4, stdout=b"index.json is stale \xff\n")

        fake = types.SimpleNamespace(run=run, PIPE=-1, STDOUT=-2)
        clock = mock.Mock(side_effect=[5.0, 5.125])
        with mock.patch.object(self.mod, "subprocess", fake), \
                mock.patch.object(self.mod.time, "perf_counter", clock):
            elapsed, rc, output = self.mod.run_once(["python3", "-c", "pass"])
        self.assertEqual((elapsed, rc), (0.125, 4))
        self.assertEqual(output, "index.json is stale \ufffd\n")
        self.assertEqual(seen["argv"], ["python3", "-c", "pass"])
        self.assertEqual(seen["kwargs"]["cwd"], self.mod.ROOT)
        self.assertEqual(seen["kwargs"]["stderr"], fake.STDOUT)

    def test_warmup_is_run_but_never_sampled(self) -> None:
        """A warmup run pays one-off costs a user never pays twice; keeping
        it would put a cold outlier into every percentile."""
        outcomes = [(9.0, 0, ""), (0.030, 0, ""), (0.010, 0, ""), (0.020, 0, "")]
        with mock.patch.object(self.mod, "run_once", side_effect=outcomes):
            measured = self.mod.measure("cli-list", ["x"], iterations=3, warmup=1)
        self.assertEqual(measured["samples_ms"], [30.0, 10.0, 20.0])
        self.assertEqual(measured["min_ms"], 10.0)
        self.assertEqual(measured["p50_ms"], 20.0)
        self.assertEqual(measured["p95_ms"], 30.0)
        self.assertEqual(measured["mean_ms"], 20.0)
        self.assertEqual((measured["iterations"], measured["warmup"]), (3, 1))

    def test_a_failing_warmup_stops_measurement_and_says_why(self) -> None:
        with mock.patch.object(self.mod, "run_once", return_value=(0.1, 2, "boom\n")), \
                self.assertRaises(SystemExit) as raised:
            self.mod.measure("route-rank", ["x"], iterations=5, warmup=2)
        message = str(raised.exception.code)
        self.assertIn("'route-rank' exited 2 during warmup", message)
        self.assertTrue(message.endswith("\nboom"))

    def test_a_failing_timed_run_is_never_a_sample(self) -> None:
        """Timing a crash measures how fast it crashes."""
        outcomes = [(0.01, 0, ""), (0.01, 1, "bad\n")]
        with mock.patch.object(self.mod, "run_once", side_effect=outcomes), \
                self.assertRaises(SystemExit) as raised:
            self.mod.measure("cli-show", ["x"], iterations=3, warmup=0)
        self.assertIn("'cli-show' exited 1; run it alone", str(raised.exception.code))
        self.assertIn("bad", str(raised.exception.code))

    def test_the_machine_is_stated_even_when_the_processor_is_not(self) -> None:
        """platform.processor() is empty on most Linux; an empty field reads
        as a measurement taken nowhere."""
        fake = types.SimpleNamespace(
            python_version=lambda: "3.12.1", platform=lambda: "Linux-6",
            machine=lambda: "x86_64", processor=lambda: "",
        )
        with mock.patch.object(self.mod, "platform", fake):
            env = self.mod.environment()
        self.assertEqual(env, {"python": "3.12.1", "platform": "Linux-6",
                               "machine": "x86_64", "processor": "x86_64"})


class CalibrationTests(unittest.TestCase):
    """measure_subset: every ratio is against the bare interpreter."""

    def setUp(self) -> None:
        self.mod = load_script("bench.py")
        self.measured: list[str] = []
        suite = {"calibration": ["c"], "fast": ["f"], "slow": ["s"]}
        mins = {"calibration": 20.0, "fast": 30.0, "slow": 70.0}

        def measure(name, argv, iterations, warmup):
            self.measured.append(name)
            return {"min_ms": mins[name], "p50_ms": mins[name] + 1, "warmup": warmup,
                    "iterations": iterations}

        for name, value in (("workloads", lambda: suite), ("measure", measure)):
            patcher = mock.patch.object(self.mod, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_ratios_divide_minimum_by_the_calibration_minimum(self) -> None:
        report = self.mod.run_suite(iterations=4, warmup=1)
        self.assertEqual(self.measured, ["calibration", "fast", "slow"])
        ratios = {k: v["ratio_to_calibration"] for k, v in report["workloads"].items()}
        self.assertEqual(ratios, {"calibration": 1.0, "fast": 1.5, "slow": 3.5})
        self.assertEqual(report["calibration_min_ms"], 20.0)
        self.assertEqual(report["calibration_p50_ms"], 21.0)
        self.assertEqual(report["generated_by"], "scripts/bench.py")
        self.assertIn("platform", report["environment"])

    def test_a_subset_always_brings_its_calibration(self) -> None:
        """Without it there is nothing to divide by, and a ratio is the only
        number that survives a change of machine."""
        report = self.mod.measure_subset(["slow"], iterations=1, warmup=0)
        self.assertEqual(sorted(report["workloads"]), ["calibration", "slow"])
        self.assertNotIn("fast", self.measured)


class VerdictHelperTests(unittest.TestCase):
    """The budget, the table, and the edge cases of the baseline builder."""

    def setUp(self) -> None:
        self.mod = load_script("bench.py")

    def test_only_interactive_workloads_answer_to_the_cold_start_budget(self) -> None:
        budget = self.mod.COLD_START_BUDGET_MS
        interactive = self.mod.INTERACTIVE
        report = {"workloads": {
            interactive[0]: entry(1.0, p50=budget + 0.5),
            interactive[1]: entry(1.0, p50=budget),
            "audit-all": entry(1.0, p50=budget * 10),
        }}
        found = self.mod.budget_failures(report)
        self.assertEqual([name for name, _ in found], [interactive[0]])
        self.assertIn(f"exceeds the {budget}ms cold-start budget", found[0][1])

    def test_the_table_shows_every_workload_and_how_it_was_sampled(self) -> None:
        buffer = io.StringIO()
        report = suite_report(**{"cli-list": entry(3.25, p50=31.0, min_ms=30.0)})
        with contextlib.redirect_stdout(buffer):
            self.mod.print_table(report)
        text = buffer.getvalue()
        self.assertIn("TestOS-1  Python 3.12.0", text)
        self.assertIn("1 warmup + 2 timed iterations, fresh process each", text)
        row = next(line for line in text.splitlines() if "cli-list" in line)
        self.assertEqual(row.split(), ["cli-list", "30.00", "31.00", "32.00", "3.25"])

    def test_one_run_or_a_zero_mean_records_no_spread(self) -> None:
        """stdev needs two samples, and a zero mean cannot be divided by."""
        single = self.mod.as_baseline([suite_report(w=entry(2.0))])
        self.assertEqual(single["workloads"]["w"]["spread_cv"], 0.0)
        self.assertEqual(single["workloads"]["w"]["allowed_regression"], 0.2)
        zero = self.mod.as_baseline([suite_report(w=entry(0.0))] * 2)
        self.assertEqual(zero["workloads"]["w"]["spread_cv"], 0.0)

    def test_redeclare_without_a_baseline_refuses(self) -> None:
        with TemporaryDirectory() as raw:
            retarget(self.mod, Path(raw).resolve())
            code, out = run_main(self.mod, "--redeclare")
        self.assertEqual(code, 1)
        self.assertIn("FAIL: no bench-baseline.json; run bench.py --write-baseline", out)

    def test_redeclare_counts_only_what_it_changed(self) -> None:
        """Run twice, the second pass must find nothing to refresh -- or the
        count it prints means nothing."""
        with TemporaryDirectory() as raw:
            retarget(self.mod, Path(raw).resolve())
            full = {n: {"spread_cv": 0.0, "p50_ms": 1.0} for n in self.mod.workloads()}
            self.mod.BASELINE.write_text(json.dumps({"workloads": full}), encoding="utf-8")
            first = run_main(self.mod, "--redeclare")
            second = run_main(self.mod, "--redeclare")
        self.assertEqual(first[0], 0)
        self.assertIn(f"refreshed {2 * len(full)} declaration(s)", first[1])
        self.assertEqual(second, (0, (
            "OK: refreshed 0 declaration(s) in bench-baseline.json; "
            "no measurement was altered\n"
        )))


class SmokeTests(unittest.TestCase):
    """--smoke is what the gate runs: runnable, not timed."""

    def setUp(self) -> None:
        self.mod = load_script("bench.py")
        suite = {"calibration": ["c"], "a": ["a"], "b": ["b"]}
        patcher = mock.patch.object(self.mod, "workloads", return_value=suite)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_every_workload_runs_once(self) -> None:
        with mock.patch.object(self.mod, "run_once", return_value=(0.0125, 0, "")) as run:
            code, out = run_main(self.mod, "--smoke")
        self.assertEqual(code, 0)
        self.assertEqual([c.args[0] for c in run.call_args_list], [["c"], ["a"], ["b"]])
        self.assertIn("OK   a                     12.5ms", out)
        self.assertIn("OK: 3 benchmark workload(s) runnable", out)

    def test_the_first_broken_workload_fails_with_its_output(self) -> None:
        outcomes = [(0.01, 0, ""), (0.01, 3, "a is broken\n"), (0.01, 0, "")]
        with mock.patch.object(self.mod, "run_once", side_effect=outcomes) as run:
            code, out = run_main(self.mod, "--smoke")
        self.assertEqual(code, 1)
        self.assertIn("FAIL: workload 'a' exited 3", out)
        self.assertIn("a is broken", out)
        self.assertEqual(run.call_count, 2, "a broken harness must stop, not keep timing")
        self.assertNotIn("runnable", out)


class BenchMainTests(unittest.TestCase):
    """The modes, what each writes, and the regression verdict."""

    def setUp(self) -> None:
        self.mod = load_script("bench.py")
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        retarget(self.mod, self.root)
        self.runs: list[tuple[int, int]] = []

    def drive(self, reports: list[dict], *args: str) -> tuple[int, str]:
        queue = list(reports)

        def run_suite(iterations, warmup):
            self.runs.append((iterations, warmup))
            return queue.pop(0)

        with mock.patch.object(self.mod, "run_suite", run_suite):
            return run_main(self.mod, *args)

    def history(self) -> list[Path]:
        return sorted((self.root / ".agtmls" / "runs").glob("bench-*.json"))

    def baseline(self, **ratios: float) -> None:
        self.mod.BASELINE.write_text(json.dumps({"workloads": {
            name: {"ratio_to_calibration": value, "spread_cv": 0.0}
            for name, value in ratios.items()
        }}), encoding="utf-8")

    def test_modes_dispatch_to_their_own_handler(self) -> None:
        for flag, handler in (("--smoke", "smoke"), ("--scaling", "scaling")):
            with mock.patch.object(self.mod, handler, return_value=7) as called:
                self.assertEqual(run_main(self.mod, flag)[0], 7, flag)
            called.assert_called_once_with()
        with mock.patch.object(self.mod, "redeclare", return_value=7) as called:
            self.assertEqual(run_main(self.mod, "--redeclare")[0], 7)
        called.assert_called_once_with(self.mod.BASELINE)
        self.assertEqual(self.runs, [], "a dispatched mode must not measure")

    def test_check_can_be_held_to_another_machines_baseline(self) -> None:
        """Ratios recorded on a laptop did not transfer to a CI runner: the
        first CI run flagged every workload at +37-64% with nothing changed.
        CI keeps its own baseline, recorded on the runner."""
        ci = self.root / "bench-baseline.ci.json"
        ci.write_text(json.dumps({"workloads": {"w": {"ratio_to_calibration": 4.8, "spread_cv": 0.0}}}),
                      encoding="utf-8")
        self.baseline(w=3.0)
        code, out = self.drive([suite_report(w=entry(4.8))], "--check", "--check-repeats", "1",
                               "--baseline", str(ci))
        self.assertEqual(code, 0, out)
        code, out = self.drive([suite_report(w=entry(4.8))], "--check", "--check-repeats", "1")
        self.assertEqual(code, 1, "the laptop baseline still judges a laptop-shaped run")

    def test_a_missing_named_baseline_is_named(self) -> None:
        code, out = self.drive([suite_report(w=entry(2.0))], "--check", "--check-repeats", "1",
                               "--baseline", str(self.root / "bench-baseline.ci.json"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: no bench-baseline.ci.json; run bench.py --write-baseline", out)

    def test_recording_another_baseline_leaves_the_published_results_alone(self) -> None:
        """benchmarks/results/ and BENCHMARKS.md describe the recorded
        machine; a CI baseline is a gate reference, not a publication."""
        ci = self.root / "bench-baseline.ci.json"
        code, out = self.drive([suite_report(w=entry(2.0))], "--write-baseline", "--repeats", "1",
                               "--baseline", str(ci))
        self.assertEqual(code, 0, out)
        self.assertIn("wrote bench-baseline.ci.json", out)
        self.assertEqual(json.loads(ci.read_text(encoding="utf-8"))["workloads"]["w"]["ratio_to_calibration"], 2.0)
        self.assertFalse(self.mod.BASELINE.exists())
        self.assertFalse(self.mod.RESULTS.exists())

    def test_a_plain_run_measures_once_and_writes_only_local_history(self) -> None:
        """A run in CI must not dirty the tree, so neither the baseline nor
        benchmarks/results/ may be written."""
        code, out = self.drive([suite_report(w=entry(2.0))], "--iterations", "4",
                               "--warmup", "2")
        self.assertEqual(code, 0)
        self.assertEqual(self.runs, [(4, 2)])
        self.assertNotIn("suite run", out)
        self.assertEqual([p.name for p in self.history()], ["bench-2026-01-01T000000Z.json"])
        self.assertFalse(self.mod.BASELINE.exists())
        self.assertFalse(self.mod.RESULTS.exists())

    def test_json_output_is_the_run_record_only(self) -> None:
        code, out = self.drive([suite_report(w=entry(2.0))], "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["workloads"]["w"]["ratio_to_calibration"], 2.0)

    def test_history_is_capped(self) -> None:
        runs = self.root / ".agtmls" / "runs"
        runs.mkdir(parents=True)
        for day in range(1, self.mod.RETAINED_RUNS + 3):
            (runs / f"bench-2000-01-{day:02d}T000000Z.json").write_text("{}", encoding="utf-8")
        (runs / "gate-1999-01-01T000000Z.json").write_text("{}", encoding="utf-8")
        self.drive([suite_report(w=entry(2.0))])
        names = [p.name for p in self.history()]
        self.assertEqual(len(names), self.mod.RETAINED_RUNS)
        self.assertEqual(names[-1], "bench-2026-01-01T000000Z.json")
        self.assertNotIn("bench-2000-01-03T000000Z.json", names)
        self.assertIn("bench-2000-01-04T000000Z.json", names)
        self.assertTrue((runs / "gate-1999-01-01T000000Z.json").exists())

    def test_write_baseline_records_the_spread_of_several_runs(self) -> None:
        reports = [suite_report(f"2026-01-0{i}T00:00:00Z", w=entry(r))
                   for i, r in ((1, 2.0), (2, 2.4))]
        code, out = self.drive(reports, "--write-baseline", "--repeats", "2")
        self.assertEqual(code, 0)
        self.assertIn("suite run 1 of 2", out)
        self.assertIn("suite run 2 of 2", out)
        self.assertIn("wrote bench-baseline.json and benchmarks/results/latency.json", out)
        baseline = json.loads(self.mod.BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(baseline["suite_runs"], 2)
        self.assertEqual(baseline["workloads"]["w"]["ratio_to_calibration"], 2.0)
        self.assertGreater(baseline["workloads"]["w"]["spread_cv"], 0.0)
        latency = json.loads((self.mod.RESULTS / "latency.json").read_text(encoding="utf-8"))
        self.assertEqual(latency["generated_at"], "2026-01-02T00:00:00Z", "the last run")
        self.assertEqual(self.history(), [], "a baseline is not a history entry")

    def test_check_without_a_baseline_fails(self) -> None:
        code, out = self.drive([suite_report(w=entry(2.0))], "--check", "--check-repeats", "1")
        self.assertEqual(code, 1)
        self.assertIn("FAIL: no bench-baseline.json; run bench.py --write-baseline", out)

    def test_check_judges_the_best_of_its_runs(self) -> None:
        """Comparing one run against a minimum-of-five baseline flagged a
        workload at +33% with nothing touching it. Only if every run is slow
        is it a regression -- for the ratio and for the cold-start P50."""
        budget = self.mod.COLD_START_BUDGET_MS
        name = self.mod.INTERACTIVE[0]
        self.baseline(**{name: 2.0})
        noisy = [
            suite_report(**{name: entry(3.0, p50=budget * 2)}),
            suite_report(**{name: entry(2.1, p50=budget - 1)}),
            suite_report(**{name: entry(2.9, p50=budget * 3)}),
        ]
        code, out = self.drive(noisy, "--check")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.runs), self.mod.CHECK_REPEATS)
        self.assertIn("suite run 3 of 3", out)
        self.assertIn("OK: 1 workload(s) within 20% of baseline; interactive P50 under", out)
        recorded = json.loads(self.history()[-1].read_text(encoding="utf-8"))
        self.assertEqual(recorded["workloads"][name]["ratio_to_calibration"], 2.1)
        self.assertEqual(recorded["workloads"][name]["p50_ms"], budget - 1)

    def test_check_fails_on_a_regression_and_on_a_blown_budget(self) -> None:
        budget = self.mod.COLD_START_BUDGET_MS
        name = self.mod.INTERACTIVE[0]
        self.baseline(**{name: 2.0, "audit-all": 5.0})
        slow = suite_report(**{name: entry(2.1, p50=budget + 5), "audit-all": entry(6.5)})
        code, out = self.drive([slow, slow], "--check", "--check-repeats", "2")
        self.assertEqual(code, 1)
        self.assertIn("FAIL: audit-all: 6.50x calibration against a baseline of 5.00x", out)
        self.assertIn(f"FAIL: {name}: P50 {budget + 5}ms exceeds", out)
        self.assertIn("FAIL: 2 performance problem(s)", out)

    def test_zero_check_repeats_still_measures_once(self) -> None:
        self.baseline(w=2.0)
        code, out = self.drive([suite_report(w=entry(2.0))], "--check", "--check-repeats", "0")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.runs), 1)
