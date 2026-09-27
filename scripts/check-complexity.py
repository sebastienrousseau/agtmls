#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Hold every function to the complexity ceilings, against a shrinking baseline.

~/Code/AGENTS.md section 0: cyclomatic 10, cognitive 15, Halstead
difficulty 30, 60 lines per function and 500 per file. Code over a ceiling
when this check arrived is recorded in `complexity-baseline.json`; it may
not get worse, and nothing new may join it. The baseline only shrinks:
when a recorded function improves, the check fails until `--write` records
the lower number, so a refactor cannot be quietly undone later.

Production code only (`scripts/`, `src/`, `fuzz/`); tests are exempt.
Another repository can hold its code to the same ceilings with `--root`,
`--paths` and `--baseline` (agtmls-spec does, from its CI checkout of
this one).

    python3 scripts/check-complexity.py            # check
    python3 scripts/check-complexity.py --write    # record improvements
    python3 scripts/check-complexity.py --root ../agtmls-spec --paths conformance \\
        --baseline ../agtmls-spec/complexity-baseline.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import complexity  # noqa: E402  (scripts path first)

BASELINE = ROOT / "complexity-baseline.json"
SCOPE = ("scripts", "src", "fuzz")


def sources(root: Path, scope: tuple[str, ...] = SCOPE) -> list[Path]:
    return sorted(p for top in scope for p in (root / top).rglob("*.py") if "__pycache__" not in p.parts)


def measure(root: Path, scope: tuple[str, ...] = SCOPE) -> dict[str, dict[str, dict[str, float]]]:
    """{"functions": {"path::name": {metric: value}}, "files": {"path": {"lines": n}}},
    holding only what is over a ceiling."""
    functions: dict[str, dict[str, float]] = {}
    files: dict[str, dict[str, float]] = {}
    for path in sources(root, scope):
        rel = path.relative_to(root).as_posix()
        for fn in complexity.measure_file(path):
            over = fn.over()
            if over:
                key = f"{rel}::{fn.name}"
                previous = functions.get(key, {})
                functions[key] = {m: max(v, previous.get(m, 0)) for m, v in {**previous, **over}.items()}
        lines = complexity.file_lines(path)
        if lines > complexity.FILE_LINES:
            files[rel] = {"lines": lines}
    return {"functions": functions, "files": files}


def _changes(key: str, now: dict[str, float], then: dict[str, float]) -> tuple[list[str], list[str]]:
    """One function's or file's (regressions, unrecorded improvements)."""
    regressions: list[str] = []
    improvements: list[str] = []
    for metric, value in sorted(now.items()):
        recorded = then.get(metric)
        if recorded is None:
            regressions.append(f"{key}: {metric} {value} is over its ceiling and not in the baseline")
        elif value > recorded:
            regressions.append(f"{key}: {metric} rose from {recorded} to {value}")
        elif value < recorded:
            improvements.append(f"{key}: {metric} fell from {recorded} to {value}")
    improvements += [
        f"{key}: {metric} ({recorded}) is now within its ceiling or gone"
        for metric, recorded in sorted(then.items()) if metric not in now
    ]
    return regressions, improvements


def compare(current: dict, baseline: dict) -> tuple[list[str], list[str]]:
    """(regressions, improvements not yet recorded)."""
    regressions: list[str] = []
    improvements: list[str] = []
    for kind in ("functions", "files"):
        now, then = current.get(kind, {}), baseline.get(kind, {})
        for key in sorted({*now, *then}):
            worse, better = _changes(key, now.get(key, {}), then.get(key, {}))
            regressions += worse
            improvements += better
    return regressions, improvements


def payload(current: dict) -> dict:
    return {
        "schema_version": 1,
        "generated_by": "scripts/check-complexity.py --write",
        "ceilings": {**complexity.CEILINGS, "file_lines": complexity.FILE_LINES},
        **current,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="record the current offenders as the baseline")
    parser.add_argument("--root", type=Path, help="the repository to measure (default: this one)")
    parser.add_argument("--paths", nargs="+", help=f"directories under the root (default: {' '.join(SCOPE)})")
    parser.add_argument("--baseline", type=Path, help=f"the baseline file (default: {BASELINE.name} in this one)")
    args = parser.parse_args()
    root = (args.root or ROOT).resolve()
    baseline_path = args.baseline or BASELINE

    current = measure(root, tuple(args.paths or SCOPE))
    if args.write:
        baseline_path.write_text(json.dumps(payload(current), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {baseline_path.name}: {len(current['functions'])} function(s), "
              f"{len(current['files'])} file(s) over a ceiling")
        return 0
    if not baseline_path.exists():
        print(f"FAIL: no {baseline_path.name}; run check-complexity.py --write")
        return 1
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    regressions, improvements = compare(current, baseline)
    for line in regressions:
        print(f"FAIL: {line}")
    for line in improvements:
        print(f"FAIL: {line}; record it with check-complexity.py --write")
    if regressions or improvements:
        print(f"\nFAIL: {len(regressions)} regression(s), {len(improvements)} unrecorded improvement(s)")
        return 1
    print(f"OK: no function or file got more complex; {len(current['functions'])} function(s) "
          f"and {len(current['files'])} file(s) remain over a ceiling")
    return 0


if __name__ == "__main__":
    sys.exit(main())
