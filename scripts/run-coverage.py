#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Measure test coverage, and refuse to let it fall.

Criterion 1.2 asks for coverage of the public surface. Nothing measured it,
so the number was unknown -- and an unknown number is not a high one. The
first measurement put the unit suite at 21% of everything and 77% of the
library core.

Two scopes, because they answer different questions
---------------------------------------------------

**core** -- the library the product's trust rests on: `scripts/_lib/` and
`src/agtmls/`. Digests, lockfiles, the command surface, the packaged entry
point. This is what decides whether an installed skill is the skill that was
published, and it is measured from the unit suite alone, in-process, so the
number reflects tests rather than incidental execution.

**all** -- every script, measured while the whole gate runs with subprocess
tracing on. Most of this repository's work happens in child processes, so a
parent-only measurement would report a number with no relationship to what is
exercised. This scope is honest about a different thing: which code any test
touches at all.

A floor, not a target
---------------------

`coverage-floor.json` is committed and may rise, never fall. A target
everyone is working toward gets negotiated down on a busy week; a floor that
already holds has to be argued with. When the measurement beats the floor,
this says so and `--update` records it.

`coverage` is not in the standard library, so this cannot join the 66-check
gate without giving up the gate being stdlib-only and runnable offline. It
runs in CI, and locally whenever someone installs the tool.

    python3 scripts/run-coverage.py                 # core, against the floor
    python3 scripts/run-coverage.py --scope all     # everything, via the gate
    python3 scripts/run-coverage.py --update        # raise the floor to what holds
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLOOR = ROOT / "coverage-floor.json"
#: The library the product's trust rests on.
CORE = ("scripts/_lib/*", "src/agtmls/*")


def coverage_cmd() -> list[str]:
    """The coverage executable, however it is reachable."""
    found = shutil.which("coverage")
    if found:
        return [found]
    probe = subprocess.run(
        [sys.executable, "-c", "import coverage"], capture_output=True, check=False
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "coverage"]
    raise SystemExit(
        "FAIL: coverage is not installed; run `python3 -m pip install coverage`, "
        "or let the CI job measure it"
    )


def floors() -> dict[str, float]:
    if not FLOOR.exists():
        return {}
    return json.loads(FLOOR.read_text(encoding="utf-8")).get("floors", {})


def measure(scope: str) -> float:
    """Run the suite under coverage and return the percentage for `scope`."""
    tool = coverage_cmd()
    for stale in ROOT.glob(".coverage*"):
        stale.unlink()

    with tempfile.TemporaryDirectory(prefix="agtmls-cov-") as raw:
        # Subprocess tracing: coverage.process_startup() runs at interpreter
        # start in every child that inherits PYTHONPATH.
        hook = Path(raw)
        (hook / "sitecustomize.py").write_text(
            "import coverage\ncoverage.process_startup()\n", encoding="utf-8"
        )
        env = dict(os.environ)
        env["COVERAGE_PROCESS_START"] = str(ROOT / "pyproject.toml")
        env["PYTHONPATH"] = os.pathsep.join(
            [str(hook)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )

        target = "run-unit-tests.py" if scope == "core" else "run-all-checks.py"
        run = subprocess.run(
            [*tool, "run", str(ROOT / "scripts" / target)],
            cwd=ROOT, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        if run.returncode != 0:
            print(run.stdout.rstrip())
            raise SystemExit(f"FAIL: {target} failed under coverage; fix that first")

        subprocess.run([*tool, "combine", "-q"], cwd=ROOT, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        report = [*tool, "report"]
        if scope == "core":
            report += ["--include", ",".join(CORE)]
        proc = subprocess.run(report, cwd=ROOT, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

    print(proc.stdout.rstrip())
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("TOTAL"):
            return float(line.split()[-1].rstrip("%"))
    raise SystemExit("FAIL: coverage produced no TOTAL line; was anything measured?")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scope", choices=["core", "all"], default="core",
                        help="core: the library, from the unit suite. all: every script, via the gate")
    parser.add_argument("--update", action="store_true",
                        help="raise the recorded floor to what currently holds")
    args = parser.parse_args()

    measured = measure(args.scope)
    recorded = floors()
    floor = float(recorded.get(args.scope, 0.0))
    print()
    print(f"{args.scope}: {measured:.1f}% against a floor of {floor:.1f}%")

    if args.update:
        if measured < floor:
            print(f"FAIL: refusing to lower the {args.scope} floor from {floor:.1f}% "
                  f"to {measured:.1f}%; a floor that moves down is a target")
            return 1
        payload = json.loads(FLOOR.read_text(encoding="utf-8")) if FLOOR.exists() else {}
        payload.setdefault("schema_version", 1)
        payload.setdefault("floors", {})
        payload["floors"][args.scope] = round(measured, 1)
        payload["note"] = (
            "Floors may rise and must never fall. core is the library measured "
            "from the unit suite; all is every script measured while the gate runs."
        )
        FLOOR.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"recorded {args.scope} floor at {measured:.1f}%")
        return 0

    if measured + 0.05 < floor:
        print(f"FAIL: {args.scope} coverage fell below its floor by "
              f"{floor - measured:.1f} points. Add the tests back, or lower the "
              "floor deliberately in coverage-floor.json and say why.")
        return 1
    if measured > floor + 0.5:
        print(f"note: the {args.scope} floor could be raised to {measured:.1f}% "
              "(run with --update)")
    print(f"OK: {args.scope} coverage holds at {measured:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
