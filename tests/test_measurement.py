# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Benchmarks, and the proof that the local surface stays offline."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import CLI, ROOT, load_script, skill_text  # noqa: F401  (used by the cases below)


class BenchmarkTests(unittest.TestCase):
    """bench.py — the file that has to be right for any timing claim to be."""

    def setUp(self) -> None:
        self.mod = load_script("bench.py")

    def test_percentile_is_nearest_rank(self) -> None:
        """An interpolated P95 reports a duration nobody observed."""
        samples = [10.0, 20.0, 30.0, 40.0]
        self.assertIn(self.mod.percentile(samples, 0.50), samples)
        self.assertIn(self.mod.percentile(samples, 0.95), samples)
        self.assertEqual(self.mod.percentile(samples, 0.95), 40.0)
        self.assertEqual(self.mod.percentile([7.0], 0.50), 7.0)

    def test_threshold_never_drops_below_the_floor(self) -> None:
        """Criterion 3.2's 20% is a floor, not a default."""
        self.assertAlmostEqual(
            self.mod.threshold_for({"spread_cv": 0.0}), self.mod.REGRESSION_THRESHOLD
        )
        self.assertAlmostEqual(
            self.mod.threshold_for({"spread_cv": 0.01}), self.mod.REGRESSION_THRESHOLD
        )

    def test_threshold_widens_with_measured_spread(self) -> None:
        """A workload too noisy to gate at 20% gets the headroom it needs."""
        wide = self.mod.threshold_for({"spread_cv": 0.18})
        self.assertGreater(wide, self.mod.REGRESSION_THRESHOLD)
        self.assertAlmostEqual(wide, 1.0 + self.mod.NOISE_SIGMAS * 0.18)

    def test_regression_is_reported_against_the_recorded_allowance(self) -> None:
        baseline = {"workloads": {"cli-list": {"ratio_to_calibration": 3.0, "spread_cv": 0.0}}}
        clean = {"workloads": {"cli-list": {"ratio_to_calibration": 3.3}}}
        slower = {"workloads": {"cli-list": {"ratio_to_calibration": 4.2}}}
        self.assertEqual(self.mod.regressions(clean, baseline), [])
        found = self.mod.regressions(slower, baseline)
        self.assertEqual([name for name, _ in found], ["cli-list"])
        self.assertIn("allowed 20%", found[0][1])

    def test_missing_baseline_entry_is_a_failure_not_a_pass(self) -> None:
        """A workload with no baseline must not silently count as fine."""
        found = self.mod.regressions(
            {"workloads": {"new-thing": {"ratio_to_calibration": 1.0}}}, {"workloads": {}}
        )
        self.assertEqual([name for name, _ in found], ["new-thing"])

    def test_baseline_records_the_spread_it_gates_on(self) -> None:
        def report(ratio: float) -> dict:
            return {
                "generated_at": "2026-01-01T00:00:00Z",
                "environment": {"python": "3.12.0"},
                "workloads": {
                    "cli-list": {
                        "ratio_to_calibration": ratio,
                        "min_ms": 30.0, "p50_ms": 31.0, "p95_ms": 33.0,
                    }
                },
            }
        baseline = self.mod.as_baseline([report(3.0), report(3.3), report(3.6)])
        entry = baseline["workloads"]["cli-list"]
        self.assertEqual(entry["ratio_to_calibration"], 3.0)  # the best seen
        self.assertGreater(entry["spread_cv"], 0.0)
        self.assertEqual(baseline["suite_runs"], 3)

    def test_redeclare_refuses_when_the_workloads_changed(self) -> None:
        """Declarations can be refreshed in place; measurements cannot.

        Re-running the suite to pick up a changed declaration would replace a
        baseline recorded on an idle machine with one recorded on whatever
        machine was free, and the absolute figures only mean anything from an
        unsaturated one. But if the workload set itself moved, the numbers no
        longer describe the suite and must be re-measured.
        """
        module = load_script("bench.py")
        with tempfile.TemporaryDirectory() as raw:
            baseline = Path(raw) / "bench-baseline.json"
            baseline.write_text(json.dumps({
                "workloads": {"calibration": {"spread_cv": 0.0, "p50_ms": 1.0}},
            }), encoding="utf-8")
            original = module.BASELINE
            module.BASELINE = baseline
            try:
                self.assertEqual(module.redeclare(), 1, "a changed workload set must refuse")
                full = {name: {"spread_cv": 0.0, "p50_ms": 1.0} for name in module.workloads()}
                baseline.write_text(json.dumps({"workloads": full}), encoding="utf-8")
                self.assertEqual(module.redeclare(), 0)
                refreshed = json.loads(baseline.read_text(encoding="utf-8"))
            finally:
                module.BASELINE = original
        for name, entry in refreshed["workloads"].items():
            self.assertEqual(entry["interactive"], name in module.INTERACTIVE)
            self.assertEqual(entry["p50_ms"], 1.0, "a measurement must not be touched")

    def test_the_baseline_declares_which_workloads_are_interactive(self) -> None:
        """Criterion 3.10's budget has nothing to bind to otherwise."""
        module = load_script("bench.py")
        recorded = json.loads((ROOT / "bench-baseline.json").read_text(encoding="utf-8"))
        for name, entry in recorded["workloads"].items():
            self.assertIn("interactive", entry, f"{name} does not say whether it is interactive")
            self.assertEqual(entry["interactive"], name in module.INTERACTIVE)

    def test_the_gate_runs_smoke_not_the_timing_check(self) -> None:
        """--check compares ratios and needs an idle machine.

        In the ten-leg matrix it would report shared-runner noise as
        regressions until people learned to ignore the gate.
        """
        checks = json.loads((ROOT / "checks.json").read_text(encoding="utf-8"))["checks"]
        self.assertIn("bench.py --smoke", checks)
        self.assertNotIn("bench.py --check", checks)

    def test_committed_baseline_covers_every_workload(self) -> None:
        recorded = json.loads((ROOT / "bench-baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(
            sorted(recorded["workloads"]), sorted(self.mod.workloads()),
            "a workload was added or renamed without re-recording the baseline",
        )


class OfflineGuaranteeTests(unittest.TestCase):
    """"No telemetry" has to be a control, not a code review.

    Absence of a telemetry client today says nothing about the next
    dependency or the next well-meant crash reporter. For a local-first tool
    whose whole positioning is that your skills never reach us, the claim
    needs something that fails when it stops being true.
    """

    def test_the_offline_proof_runs_in_the_gate(self) -> None:
        checks = json.loads((ROOT / "checks.json").read_text(encoding="utf-8"))["checks"]
        self.assertIn("smoke-offline.py", checks)

    def test_the_block_records_and_refuses(self) -> None:
        """The injected sitecustomize must do both.

        Refusing without recording would report a clean run for a call that
        was attempted, which is the failure mode that matters: a telemetry
        ping whose exception is swallowed still exits 0.
        """
        module = load_script("smoke-offline.py")
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            injected = workspace / "inject"
            injected.mkdir()
            (injected / "sitecustomize.py").write_text(module.SITECUSTOMIZE, encoding="utf-8")
            log = workspace / "attempts.log"
            env = module.blocked_environment(injected, log)
            proc = subprocess.run(
                [sys.executable, "-c",
                 "import urllib.request\n"
                 "try:\n"
                 "    urllib.request.urlopen('http://example.invalid', timeout=1)\n"
                 "except Exception:\n"
                 "    pass\n"],
                env=env, capture_output=True, text=True, check=False,
            )
            recorded = module.attempts(log)
        self.assertEqual(proc.returncode, 0, "the swallowed call must still exit 0")
        self.assertTrue(recorded, "a swallowed network call was not recorded")
        self.assertIn("example.invalid", "".join(recorded))

    def test_the_local_surface_covers_what_a_consumer_runs(self) -> None:
        """A proof that only covered `--help` would prove nothing."""
        module = load_script("smoke-offline.py")
        covered = {argv[0] for argv in module.COMMANDS}
        for command in ("list", "search", "show", "stats", "audit", "index"):
            self.assertIn(command, covered, f"{command} is not exercised offline")
