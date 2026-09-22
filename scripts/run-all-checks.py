#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Run the full AgtMLS local validation gate.

`checks.json` is the gate, and nothing else is. This file used to carry a
second copy of that list plus a third list naming every script to
byte-compile. The compile list had already drifted: it named 77 scripts while
81 were on disk, and one of the four it omitted was `audit-skill.py`, the
security analyzer. A gate described in three places eventually describes
something that is not what runs. `validate-python-scripts.py` already parses
every `scripts/*.py` found on disk, which is both stronger and self-updating,
so the compile pass is gone rather than repaired.

Checks are independent processes, so they are dispatched concurrently and
**every** failure is reported. Returning on the first one cost one fix per CI
round trip. The pool is threads rather than processes on purpose: the work
happens in child processes, so the parent only waits on them, and threads
avoid pickling a runner that is loaded by path in the test suite.

Two checks are scheduled alone, because they write inside the working tree
while they run: `make install` regenerates `completions/` and `share/man/` in
place, and the install-verification smoke test tampers with a real skill to
prove a drifted registry is refused. A concurrent reader of either is a flaky
gate, so tree-mutating checks do not share the pool. See EXCLUSIVE below.

    python3 scripts/run-all-checks.py              # all of it, concurrently
    python3 scripts/run-all-checks.py --jobs 1     # serial, for bisecting
    python3 scripts/run-all-checks.py --format json
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
MANIFEST = ROOT / "checks.json"
RUNS_DIR = ROOT / ".agtmls" / "runs"

# Checks that write inside the working tree and therefore cannot share the
# pool with readers of the same files. This annotates manifest entries; it is
# not a second copy of the manifest, and a unit test fails if a name here
# stops being a check.
#
#   smoke-make-install.py   runs `make install`, whose prerequisites
#                           regenerate completions/ and share/man/ in place.
#   smoke-install-verify.py deliberately tampers with
#                           skills/writing-plans/SKILL.md to prove `install`
#                           refuses a drifted registry, restoring it in a
#                           `finally`. Harmless when the gate was serial; with
#                           a pool, any concurrent reader of skills/ can
#                           observe the tampered state. It was found exactly
#                           once in ten gate runs, as `generate-skill-index.py
#                           --check` reporting index.json stale, because the
#                           tamper window is one `install` invocation long.
#
# The list was derived by measurement, not by reading: run each check alone
# while polling mtime and size of every file in the tree, and see which ones
# move. Re-run that when adding a check that writes anything.
EXCLUSIVE = frozenset({"smoke-make-install.py", "smoke-install-verify.py"})

# Enough history to see a trend in gate duration, bounded so the directory
# does not grow for the life of the checkout.
RETAINED_RUNS = 50


@dataclass(frozen=True)
class CheckResult:
    """One check, its outcome, and what it cost."""

    check: str
    returncode: int
    duration_s: float
    output: str


def manifest_checks() -> list[str]:
    """The gate, read from its single source of truth."""
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["checks"]


def run_one(check: str, scripts_dir: Path = SCRIPTS) -> CheckResult:
    parts = shlex.split(check)
    cmd = [sys.executable, str(scripts_dir / parts[0]), *parts[1:]]
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return CheckResult(check, proc.returncode, time.perf_counter() - started, proc.stdout)


def default_jobs() -> int:
    return max(1, min(8, os.cpu_count() or 1))


def run_checks(
    checks: list[str], jobs: int | None = None, scripts_dir: Path = SCRIPTS
) -> list[CheckResult]:
    """Run every check and return every result, in manifest order.

    Never short-circuits: a caller that wants the first failure can find it,
    but a caller that wants to fix everything in one pass needs all of them.
    """
    jobs = jobs or default_jobs()
    # Indexed rather than keyed by name: a manifest that listed the same check
    # twice would otherwise collapse to one result and under-report the gate.
    shared = [(i, c) for i, c in enumerate(checks) if shlex.split(c)[0] not in EXCLUSIVE]
    alone = [(i, c) for i, c in enumerate(checks) if shlex.split(c)[0] in EXCLUSIVE]

    results: dict[int, CheckResult] = {}
    if shared:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            for index, result in pool.map(
                lambda pair: (pair[0], run_one(pair[1], scripts_dir)), shared
            ):
                results[index] = result
    for index, check in alone:
        results[index] = run_one(check, scripts_dir)
    return [results[i] for i in range(len(checks))]


def record(results: list[CheckResult], wall_s: float, jobs: int) -> Path:
    """Persist the run so gate duration is a measurement, not a memory."""
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "jobs": jobs,
        "wall_s": round(wall_s, 3),
        "cpu_s": round(sum(r.duration_s for r in results), 3),
        "checks": len(results),
        "failed": [r.check for r in results if r.returncode != 0],
        "durations": {r.check: round(r.duration_s, 3) for r in results},
    }
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"gate-{payload['generated_at'].replace(':', '')}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # A record per run grows without bound otherwise. Names sort
    # chronologically, so the oldest are the ones to drop.
    stale = sorted(RUNS_DIR.glob("gate-*.json"))[:-RETAINED_RUNS]
    for old in stale:
        old.unlink()
    return path


def report(results: list[CheckResult], wall_s: float, jobs: int) -> None:
    failures = [r for r in results if r.returncode != 0]
    for result in failures:
        print(f"\n=== FAIL ({result.returncode}) {result.check} ===")
        print(result.output.rstrip())

    print()
    slowest = sorted(results, key=lambda r: r.duration_s, reverse=True)[:5]
    for result in slowest:
        print(f"  {result.duration_s:6.2f}s  {result.check}")
    serial = sum(r.duration_s for r in results)
    print(
        f"\n{len(results)} check(s) in {wall_s:.2f}s wall "
        f"({serial:.2f}s serial, {jobs} job(s))"
    )
    if failures:
        print(f"FAIL: {len(failures)} of {len(results)} check(s) failed:")
        for result in failures:
            print(f"  - {result.check}")
    else:
        print(f"OK: {len(results)} check(s) passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--jobs",
        type=int,
        default=default_jobs(),
        help="concurrent checks (default: min(8, cpu count); 1 to serialise)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="human table, or the machine-readable run record",
    )
    args = parser.parse_args()

    checks = manifest_checks()
    started = time.perf_counter()
    results = run_checks(checks, jobs=args.jobs)
    wall = time.perf_counter() - started

    path = record(results, wall, args.jobs)
    if args.format == "json":
        print(json.dumps(
            {"run": str(path.relative_to(ROOT)),
             "results": [asdict(r) for r in results]},
            indent=2,
        ))
    else:
        report(results, wall, args.jobs)

    return 1 if any(r.returncode != 0 for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
