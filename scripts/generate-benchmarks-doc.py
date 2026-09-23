#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Render every measured number in BENCHMARKS.md from benchmarks/results/.

BENCHMARKS.md was written by hand around bench.py's output, and nothing
compared the two. Its scaling table said digest grew x9.5 and pairwise
scoring x73.4 for a tenfold registry, while scaling.json -- re-measured since
-- recorded x7.02 and x110.62. That is the failure laya-mlx's README shows:
a headline that its own committed data does not support.

Each measured passage now lives between markers:

    <!-- generated:scaling sources="benchmarks/results/scaling.json:<sha256>" -->
    ...
    <!-- /generated:scaling -->

`--write` re-renders every block from its sources and stamps their hashes.
`--check` fails if a block's text or a source file moved without the other,
so a re-measurement cannot silently leave the prose behind, and a number
edited by hand is caught.

    python3 scripts/generate-benchmarks-doc.py --write
    python3 scripts/generate-benchmarks-doc.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "BENCHMARKS.md"
LATENCY = ROOT / "benchmarks" / "results" / "latency.json"
SCALING = ROOT / "benchmarks" / "results" / "scaling.json"
BASELINE = ROOT / "bench-baseline.json"

BLOCK = re.compile(
    r'<!-- generated:(?P<name>[a-z-]+) sources="(?P<sources>[^"]*)" -->\n'
    r"(?P<body>.*?)"
    r"<!-- /generated:(?P=name) -->",
    re.DOTALL,
)

# Table order and labels. A workload bench.py adds later is appended, sorted.
ORDER = [
    "calibration", "cli-list", "cli-search", "cli-show", "cli-stats",
    "digest-registry", "route-rank", "audit-all", "index-check",
]
LABELS = {
    "calibration": "`calibration` (bare interpreter)",
    "digest-registry": "`digest-registry` (every skill)",
    "route-rank": "`route-rank` (TF-IDF over every description)",
    "audit-all": "`audit-all` (`--all --strict`)",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment(env: dict) -> str:
    """`macOS-26.7-arm64-arm-64bit` -> `macOS 26.7, arm64, Python 3.12.14`."""
    system, _, rest = env.get("platform", "unknown").partition("-")
    release = rest.split("-", 1)[0]
    return f"{system} {release}, {env.get('machine', '?')}, Python {env.get('python', '?')}"


def render_latency() -> str:
    latency, baseline = load(LATENCY), load(BASELINE)
    workloads = latency["workloads"]
    names = [n for n in ORDER if n in workloads] + sorted(set(workloads) - set(ORDER))
    rows = [
        f"| {LABELS.get(n, f'`{n}`')} | {w['min_ms']:.2f} | {w['p50_ms']:.2f} | {w['p95_ms']:.2f} "
        f"| {w['ratio_to_calibration']:.2f} |"
        for n, w in ((n, workloads[n]) for n in names)
    ]
    interactive = [workloads[n]["p50_ms"] for n in names if n.startswith("cli-")]
    calibration = workloads["calibration"]["p50_ms"]
    fastest = min(interactive)
    budget = baseline["cold_start_budget_ms"]
    return "\n".join([
        f"Recorded on the machine named in `bench-baseline.json`: {environment(latency['environment'])}.",
        f"One machine, {baseline['suite_runs']} suite runs. No claim is made about any other machine.",
        "",
        "| Workload | min ms | P50 ms | P95 ms | × calibration |",
        "|---|---:|---:|---:|---:|",
        *rows,
        "",
        (
            f"The {len(interactive)} `cli-*` commands are the interactive surface: P50 between "
            f"**{fastest:.0f}ms** and **{max(interactive):.0f}ms**, against the {budget:.0f}ms budget of "
            f"scorecard criterion 3.10. About {calibration:.0f}ms of that is the interpreter itself — the "
            f"calibration row — so AgtMLS's own share of the fastest command is about "
            f"{fastest - calibration:.0f}ms."
        ),
        "",
    ])


def render_thresholds() -> str:
    baseline = load(BASELINE)
    workloads = baseline["workloads"]
    floor = baseline["regression_threshold_floor"] - 1
    spreads = [w["spread_cv"] for n, w in workloads.items() if n != "calibration"]
    at_floor = [n for n, w in workloads.items() if w["allowed_regression"] <= floor + 1e-9]
    wider = sorted((n, w["allowed_regression"]) for n, w in workloads.items() if n not in at_floor)
    tail = "".join(f" and `{n}` at {allowed:.0%}" for n, allowed in wider)
    return (
        f"On the recorded machine the spreads are {min(spreads):.1%} to {max(spreads):.1%}, so "
        f"{len(at_floor)} of {len(workloads)} workloads are gated at the full {floor:.0%} of "
        f"criterion 3.2{tail}.\n"
    )


def render_scaling() -> str:
    scaling = load(SCALING)
    rows = sorted(scaling["rows"], key=lambda row: row["skills"])
    growth = scaling["growth"]
    largest = rows[-1]

    def extrapolate(skills: int) -> float:
        return largest["pairwise_ms"] * (skills / largest["skills"]) ** 2 / 1000

    table = [f"| {row['skills']} | {row['digest_ms']:.2f} ms | {row['pairwise_ms']:.2f} ms |" for row in rows]
    return "\n".join([
        "| Skills | `skill_digest` over all | Pairwise description scoring |",
        "|---:|---:|---:|",
        *table,
        f"| **growth for ×{growth['size']:.0f}** | **×{growth['digest']:.2f}** | **×{growth['pairwise']:.2f}** |",
        "",
        (
            f"`skill_digest` measured ×{growth['digest']:.2f} for ×{growth['size']:.0f} the corpus. Pairwise "
            f"scoring measured ×{growth['pairwise']:.2f}; at {rows[0]['skills']} skills it costs "
            f"{rows[0]['pairwise_ms']:.2f}ms, and extrapolating quadratically from {largest['skills']} skills "
            f"it reaches roughly {extrapolate(1000):.1f}s at 1,000 skills and {extrapolate(3000):.1f}s at 3,000."
        ),
        "",
    ])


BLOCKS = {
    "latency": ((LATENCY, BASELINE), render_latency),
    "thresholds": ((BASELINE,), render_thresholds),
    "scaling": ((SCALING,), render_scaling),
}


def stamp(paths: tuple[Path, ...]) -> str:
    return ",".join(f"{path.relative_to(ROOT).as_posix()}:{digest(path)}" for path in paths)


def rendered(text: str) -> tuple[str, list[str]]:
    """The document with every block re-rendered, and the blocks that differed."""
    stale: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in BLOCKS:
            stale.append(f"{name}: unknown generated block")
            return match.group(0)
        sources, render = BLOCKS[name]
        fresh = f'<!-- generated:{name} sources="{stamp(sources)}" -->\n{render()}<!-- /generated:{name} -->'
        if fresh != match.group(0):
            stale.append(name)
        return fresh

    out = BLOCK.sub(replace, text)
    missing = sorted(set(BLOCKS) - {m.group("name") for m in BLOCK.finditer(text)})
    stale.extend(f"{name}: no generated block in {DOC.name}" for name in missing)
    return out, stale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = DOC.read_text(encoding="utf-8")
    out, stale = rendered(text)

    if args.write:
        missing = [item for item in stale if "no generated block" in item]
        if missing:
            for item in missing:
                print(f"FAIL: {item}; add its markers first")
            return 1
        DOC.write_text(out, encoding="utf-8")
        print(f"wrote {DOC.relative_to(ROOT)} ({len(BLOCKS)} generated block(s))")
        return 0
    if args.check:
        if stale:
            for item in stale:
                print(f"FAIL: {DOC.name} block {item} does not match its results; "
                      "run generate-benchmarks-doc.py --write")
            return 1
        print(f"OK: {len(BLOCKS)} measured block(s) in {DOC.name} match benchmarks/results/")
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
