#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Measure how long AgtMLS takes, and fail when it gets slower.

This used to re-run three validators the gate already runs and print a quality
score. It measured no time at all, which left criteria 3.1, 3.2, 3.5 and 3.10
unprovable and every timing claim in the documentation unguarded.

**The method, the recorded numbers and the designs that were tried and dropped
all live in BENCHMARKS.md.** Only what a reader of this file needs is here:

- Every sample is a fresh process, so nothing is measured warm that a user
  pays for cold, and timing includes interpreter startup by design.
- `ratio_to_calibration` divides a workload's *minimum* by the *minimum* of a
  bare-interpreter run. Minimum, because noise only ever adds time; against a
  bare interpreter, because these workloads are dominated by process spawn and
  a CPU-loop calibration measured worse than no normalisation at all.
- `--check` takes the minimum across `--check-repeats` full suite runs, which
  is the same statistic `--write-baseline` records. Comparing a single run
  against a minimum-of-five baseline compares two different things, and it
  showed up as a workload flagged at +33% with nothing touching it.
- Per-workload thresholds come from the spread recorded in the baseline, never
  from a number chosen here; REGRESSION_THRESHOLD is only the floor.
- Full-gate wall time is deliberately absent: run-all-checks.py already
  records its own duration per run under .agtmls/runs/.

    python3 scripts/bench.py                  # measure and print
    python3 scripts/bench.py --smoke          # one iteration; what the gate runs
    python3 scripts/bench.py --check          # fail on a regression
    python3 scripts/bench.py --write-baseline # re-record bench-baseline.json
    python3 scripts/bench.py --scaling        # growth at 10x registry size
    python3 scripts/bench.py --scaling --record  # and publish it to benchmarks/results/
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPTS = ROOT / "scripts"

from _lib.scaling import scaling  # noqa: E402  (needs the scripts path first)
from _lib.workloads import (  # noqa: E402  (needs the scripts path first)
    COLD_START_BUDGET_MS,
    INTERACTIVE,
    workloads,
)

RESULTS = ROOT / "benchmarks" / "results"
BASELINE = ROOT / "bench-baseline.json"
HISTORY = ROOT / ".agtmls" / "runs"

# Criterion 3.2: the floor for every workload. A workload whose measured
# spread demands more headroom than this gets more; none gets less.
REGRESSION_THRESHOLD = 1.20

# How many standard deviations of a workload's own measured spread to allow
# before calling a change a regression. Three keeps false alarms rare.
NOISE_SIGMAS = 3.0

# Full suite runs behind a recorded baseline. One run cannot observe its own
# run-to-run spread, which is the quantity the threshold is derived from.
BASELINE_REPEATS = 5

# Suite runs behind a --check verdict. Fewer than the baseline, because a
# gate has to finish, but more than one: a single run's spread is what
# produces false alarms.
CHECK_REPEATS = 3

# Same policy as run-all-checks.py: enough history to see a trend, bounded so
# the directory does not grow for the life of the checkout.
RETAINED_RUNS = 50

def percentile(samples: list[float], fraction: float) -> float:
    """Nearest-rank percentile.

    Not interpolated: an interpolated P95 reports a duration that was never
    observed, which is a poor thing to put in a table of measurements.
    """
    ordered = sorted(samples)
    rank = max(1, min(len(ordered), int(-(-fraction * len(ordered) // 1))))
    return ordered[rank - 1]


def run_once(argv: list[str]) -> tuple[float, int, str]:
    """Time one run, and keep its output if it failed.

    stdout was discarded here at first, which meant a workload that failed
    inside the gate reported only its exit code: `generate-skill-index.py`
    prints "index.json is stale" to stdout, so the one line explaining the
    failure was the one line thrown away. Capturing costs a pipe; a gate
    failure nobody can diagnose costs a lot more.
    """
    started = time.perf_counter()
    proc = subprocess.run(
        argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
    )
    elapsed = time.perf_counter() - started
    return elapsed, proc.returncode, proc.stdout.decode("utf-8", "replace")


def measure(name: str, argv: list[str], iterations: int, warmup: int) -> dict[str, object]:
    for _ in range(warmup):
        _, rc, output = run_once(argv)
        if rc != 0:
            raise SystemExit(
                f"FAIL: workload {name!r} exited {rc} during warmup; run it alone to see "
                f"why, then fix it or drop it from workloads()\n{output.rstrip()}"
            )
    samples: list[float] = []
    for _ in range(iterations):
        elapsed, rc, output = run_once(argv)
        if rc != 0:
            raise SystemExit(f"FAIL: workload {name!r} exited {rc}; run it alone to see why\n{output.rstrip()}")
        samples.append(elapsed * 1000.0)
    return {
        "name": name,
        "iterations": iterations,
        "warmup": warmup,
        "p50_ms": round(percentile(samples, 0.50), 3),
        "p95_ms": round(percentile(samples, 0.95), 3),
        "mean_ms": round(statistics.fmean(samples), 3),
        "min_ms": round(min(samples), 3),
        "samples_ms": [round(s, 3) for s in samples],
    }


def environment() -> dict[str, str]:
    """Stated, not implied. A measurement without its machine is a rumour."""
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine(),
    }


def measure_subset(
    names: list[str] | None, iterations: int, warmup: int
) -> dict[str, object]:
    """Measure `names` (default: all), always including the calibration.

    Split out of run_suite so a suspected regression can be re-measured
    without paying for the whole suite again.
    """
    selected = workloads()
    if names is not None:
        wanted = set(names) | {"calibration"}
        selected = {k: v for k, v in selected.items() if k in wanted}

    measurements: dict[str, dict[str, object]] = {}
    for name, argv in selected.items():
        measurements[name] = measure(name, argv, iterations, warmup)

    # Minimums: see the module docstring. Noise only adds time, so min is the
    # least-contaminated estimate of cost, and dividing two medians compounds
    # two lots of jitter.
    calibration_min = float(measurements["calibration"]["min_ms"])
    for name, entry in measurements.items():
        entry["ratio_to_calibration"] = round(float(entry["min_ms"]) / calibration_min, 4)

    return {
        "schema_version": 1,
        "generated_by": "scripts/bench.py",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": environment(),
        "calibration_min_ms": round(calibration_min, 3),
        "calibration_p50_ms": round(float(measurements["calibration"]["p50_ms"]), 3),
        "workloads": measurements,
    }


def run_suite(iterations: int, warmup: int) -> dict[str, object]:
    return measure_subset(None, iterations, warmup)


def print_table(report: dict[str, object]) -> None:
    env = report["environment"]
    print(f"{env['platform']}  Python {env['python']}")
    first = next(iter(report["workloads"].values()))
    print(f"{first['warmup']} warmup + {first['iterations']} timed iterations, fresh process each")
    print()
    print(f"  {'workload':<18}{'min ms':>10}{'P50 ms':>10}{'P95 ms':>10}{'x calib':>10}")
    for name, entry in report["workloads"].items():
        print(
            f"  {name:<18}{entry['min_ms']:>10.2f}{entry['p50_ms']:>10.2f}"
            f"{entry['p95_ms']:>10.2f}{entry['ratio_to_calibration']:>10.2f}"
        )


def budget_failures(report: dict[str, object]) -> list[tuple[str, str]]:
    """Criterion 3.10: the interactive surfaces have a stated ceiling."""
    failures = []
    for name in INTERACTIVE:
        entry = report["workloads"].get(name)
        if entry and float(entry["p50_ms"]) > COLD_START_BUDGET_MS:
            failures.append((
                name,
                (
                    f"{name}: P50 {entry['p50_ms']}ms exceeds the "
                    f"{COLD_START_BUDGET_MS}ms cold-start budget"
                ),
            ))
    return failures


def threshold_for(record: dict[str, object]) -> float:
    """How much slower this workload may get before it counts.

    The floor is criterion 3.2's 20%. A workload whose own measured spread is
    wider than that gets NOISE_SIGMAS of headroom instead, because gating
    inside the noise produces alarms that teach people to ignore the gate.
    """
    spread = float(record.get("spread_cv", 0.0))
    return max(REGRESSION_THRESHOLD, 1.0 + NOISE_SIGMAS * spread)


def regressions(report: dict[str, object], baseline: dict[str, object]) -> list[tuple[str, str]]:
    """Ratios, not milliseconds, so a slower machine is not a regression."""
    found = []
    recorded = baseline["workloads"]
    for name, entry in report["workloads"].items():
        if name == "calibration" or name not in recorded:
            continue
        before = float(recorded[name]["ratio_to_calibration"])
        after = float(entry["ratio_to_calibration"])
        limit = threshold_for(recorded[name])
        if after > before * limit:
            found.append((
                name,
                (
                    f"{name}: {after:.2f}x calibration against a baseline of {before:.2f}x "
                    f"(+{(after / before - 1) * 100:.0f}%, allowed "
                    f"{(limit - 1) * 100:.0f}%)"
                ),
            ))
    missing = sorted(set(report["workloads"]) - set(recorded) - {"calibration"})
    for name in missing:
        found.append((name, f"{name}: no baseline; run bench.py --write-baseline"))
    return found


def as_baseline(reports: list[dict[str, object]]) -> dict[str, object]:
    """A contract, built from several full suite runs.

    Raw samples stay in benchmarks/results/, which records one run; a contract
    with hundreds of floats in it is a diff nobody reads. What is kept per
    workload is the best ratio observed and the spread across runs, which is
    what threshold_for() turns into a gate.
    """
    last = reports[-1]
    workloads_out: dict[str, dict[str, object]] = {}
    for name in last["workloads"]:
        ratios = [float(r["workloads"][name]["ratio_to_calibration"]) for r in reports]
        mean = statistics.fmean(ratios)
        spread = (statistics.stdev(ratios) / mean) if len(ratios) > 1 and mean else 0.0
        workloads_out[name] = {
            "ratio_to_calibration": round(min(ratios), 4),
            "spread_cv": round(spread, 4),
            "min_ms": last["workloads"][name]["min_ms"],
            "p50_ms": last["workloads"][name]["p50_ms"],
            "p95_ms": last["workloads"][name]["p95_ms"],
            # Declared, not inferred: COLD_START_BUDGET_MS governs the surfaces
            # a person waits on, and a budget with nothing bound to it is prose.
            "interactive": name in INTERACTIVE,
        }
    for name, record in workloads_out.items():
        record["allowed_regression"] = round(threshold_for(record) - 1.0, 4)
    return {
        "schema_version": 1,
        "generated_by": "scripts/bench.py --write-baseline",
        "generated_at": last["generated_at"],
        "recorded_on": last["environment"],
        "suite_runs": len(reports),
        "regression_threshold_floor": REGRESSION_THRESHOLD,
        "noise_sigmas": NOISE_SIGMAS,
        "cold_start_budget_ms": COLD_START_BUDGET_MS,
        "workloads": workloads_out,
    }


def redeclare(path: Path | None = None) -> int:
    """Refresh what the baseline *declares*, leaving what it *measured* alone.

    Which workloads are interactive, and how much regression each is allowed,
    are derived from this file's constants rather than from a stopwatch. When
    they change, re-running the whole suite to pick them up would replace a
    baseline recorded on an idle machine with one recorded on whatever machine
    happened to be free -- and the absolute figures in a baseline are only
    meaningful from an unsaturated one.

    So this rewrites the derived fields and refuses to touch the numbers.
    """
    path = path or BASELINE
    if not path.exists():
        print(f"FAIL: no {path.name}; run bench.py --write-baseline")
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    known = set(workloads())
    recorded = set(data.get("workloads", {}))
    if recorded != known:
        print(f"FAIL: the baseline records {sorted(recorded)} but the suite defines "
              f"{sorted(known)}; the workloads changed, so the numbers must be "
              "re-measured with --write-baseline")
        return 1

    changed = []
    for name, entry in data["workloads"].items():
        for key, value in (("interactive", name in INTERACTIVE),
                           ("allowed_regression", round(threshold_for(entry) - 1.0, 4))):
            if entry.get(key) != value:
                changed.append(f"{name}.{key}")
                entry[key] = value
    data["noise_sigmas"] = NOISE_SIGMAS
    data["regression_threshold_floor"] = REGRESSION_THRESHOLD
    data["cold_start_budget_ms"] = COLD_START_BUDGET_MS
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OK: refreshed {len(changed)} declaration(s) in {path.name}; "
          "no measurement was altered")
    return 0


def smoke() -> int:
    """One iteration of every workload. Proves the harness runs; times nothing.

    This is what belongs in the 66-check gate: a timing assertion inside a
    ten-leg matrix on shared runners is a flake generator, and `--check`
    exists for a dedicated job.
    """
    for name, argv in workloads().items():
        elapsed, rc, output = run_once(argv)
        if rc != 0:
            print(f"FAIL: workload {name!r} exited {rc}; run that command alone to see why")
            print(output.rstrip())
            return 1
        print(f"OK   {name:<18}{elapsed * 1000:>8.1f}ms")
    print(f"\nOK: {len(workloads())} benchmark workload(s) runnable")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure AgtMLS performance.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true", help="one iteration per workload; no timing assertions")
    mode.add_argument("--check", action="store_true", help="fail on a regression against bench-baseline.json")
    mode.add_argument("--write-baseline", action="store_true", help="re-record bench-baseline.json")
    mode.add_argument("--scaling", action="store_true", help="measure growth at 10x registry size")
    mode.add_argument(
        "--redeclare",
        action="store_true",
        help="refresh the baseline's derived declarations without re-measuring",
    )
    parser.add_argument("--iterations", type=int, default=20, help="timed iterations (default: 20)")
    parser.add_argument("--warmup", type=int, default=3, help="untimed iterations first (default: 3)")
    parser.add_argument(
        "--repeats",
        type=int,
        default=BASELINE_REPEATS,
        help=f"full suite runs behind a baseline (default: {BASELINE_REPEATS})",
    )
    parser.add_argument(
        "--check-repeats",
        type=int,
        default=CHECK_REPEATS,
        help=f"full suite runs behind a --check verdict (default: {CHECK_REPEATS})",
    )
    parser.add_argument("--json", action="store_true", help="emit the run record instead of a table")
    parser.add_argument(
        "--record", action="store_true",
        help="with --scaling, write benchmarks/results/scaling.json (the published result)",
    )
    parser.add_argument(
        "--baseline", type=Path, default=None,
        help="baseline to check against or record (default: bench-baseline.json). Ratios "
             "do not transfer between machines, so CI keeps its own, recorded on the runner",
    )
    args = parser.parse_args()
    baseline_path = args.baseline or BASELINE

    if args.smoke:
        return smoke()
    if args.scaling:
        return scaling(record=args.record)
    if args.redeclare:
        return redeclare(baseline_path)

    if args.write_baseline:
        # One run cannot observe its own run-to-run spread, and the spread is
        # what the per-workload threshold is derived from.
        reports = []
        for index in range(args.repeats):
            print(f"suite run {index + 1} of {args.repeats}")
            reports.append(run_suite(args.iterations, args.warmup))
        report = reports[-1]
        print()
        print_table(report)
        baseline_path.write_text(
            json.dumps(as_baseline(reports), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if baseline_path != BASELINE:
            # Another machine's baseline is a gate reference, not the
            # published measurement BENCHMARKS.md is generated from.
            print(f"\nwrote {baseline_path.name}")
            return 0
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "latency.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"\nwrote {BASELINE.relative_to(ROOT)} and {(RESULTS / 'latency.json').relative_to(ROOT)}")
        return 0

    # A --check run must be measured the way the baseline was measured, or the
    # two numbers are not comparable. The baseline takes the minimum ratio
    # across several full suite runs; so does this.
    #
    # Two earlier designs failed here and are recorded so they are not retried:
    # a single suite run flagged `route-rank` at +33% with nothing touching it,
    # and re-measuring only the suspects cleared a deliberately injected 25%
    # regression in `cli-list`, because a five-workload rerun loads the machine
    # differently from a nine-workload one.
    passes = max(1, args.check_repeats if args.check else 1)
    reports = []
    for index in range(passes):
        if passes > 1:
            print(f"suite run {index + 1} of {passes}")
        reports.append(run_suite(args.iterations, args.warmup))
    report = reports[-1]
    if passes > 1:
        for name in report["workloads"]:
            entry = report["workloads"][name]
            entry["ratio_to_calibration"] = round(
                min(float(r["workloads"][name]["ratio_to_calibration"]) for r in reports), 4
            )
            # The cold-start budget is judged the same way, so one warm run
            # cannot fail a build on its own.
            entry["p50_ms"] = round(
                min(float(r["workloads"][name]["p50_ms"]) for r in reports), 3
            )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        if passes > 1:
            print()
        print_table(report)

    # Local history, never the committed record: a --check run in CI must not
    # dirty the tree. Capped for the same reason the gate's run records are.
    HISTORY.mkdir(parents=True, exist_ok=True)
    (HISTORY / f"bench-{report['generated_at'].replace(':', '')}.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for old in sorted(HISTORY.glob("bench-*.json"))[:-RETAINED_RUNS]:
        old.unlink()

    if not args.check:
        return 0

    if not baseline_path.exists():
        print(f"\nFAIL: no {baseline_path.name}; run bench.py --write-baseline")
        return 1
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    problems = regressions(report, baseline) + budget_failures(report)

    if problems:
        print()
        for _, text in problems:
            print(f"FAIL: {text}")
        print(f"\nFAIL: {len(problems)} performance problem(s)")
        return 1

    print(f"\nOK: {len(report['workloads']) - 1} workload(s) within "
          f"{(REGRESSION_THRESHOLD - 1) * 100:.0f}% of baseline; "
          f"interactive P50 under {COLD_START_BUDGET_MS:.0f}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
