#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Conformance corpus for the skill security analyzer.

`audit --all --strict` reporting "zero findings" is only meaningful if the
analyzer has been shown to catch things. The unit tests asserted that each
detector fires on its own canonical string, which proves the regex compiles
and nothing else -- three independent evasions passed a strict audit cleanly.

Each case in evals/security/corpus.json is materialised into a temporary
directory and audited. `must_detect` entries must be found at or above the
stated severity; `must_not_detect` categories must stay silent, which is what
keeps the analyzer usable rather than merely loud.

The corpus is a data file, not a directory of fixture skills, for two reasons:
a fixture with deliberately malformed JSON or an unsigned shell script would
fail the repository's own validators, and a language-independent manifest can
be replayed against any future reimplementation of the same ruleset.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "scripts" / "audit-skill.py"
CORPUS = ROOT / "evals" / "security" / "corpus.json"
RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def materialise(case: dict, root: Path) -> Path:
    target = root / case["name"]
    target.mkdir(parents=True)
    for name, content in case["files"].items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if name.endswith((".sh", ".bash")):
            path.chmod(0o755)
    return target


def audit(target: Path) -> list[dict]:
    proc = subprocess.run(
        [sys.executable, str(AUDIT), str(target), "--strict", "--format", "json"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    try:
        return json.loads(proc.stdout)["findings"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise SystemExit(f"audit produced no JSON for {target.name}: {exc}\n{proc.stdout}\n{proc.stderr}")


FLOOR = ROOT / "evals" / "security" / "floor.json"
DEFAULT_FLOORS = {"precision": 1.0, "recall": 1.0}


def read_floors() -> dict[str, float]:
    """The precision and recall the corpus must hold; 1.0 each without a file."""
    if not FLOOR.exists():
        return dict(DEFAULT_FLOORS)
    floors = json.loads(FLOOR.read_text(encoding="utf-8")).get("floors", {})
    return {key: float(floors.get(key, DEFAULT_FLOORS[key])) for key in DEFAULT_FLOORS}


def write_floors(floors: dict[str, float]) -> None:
    FLOOR.write_text(json.dumps({
        "schema_version": 1,
        "floors": floors,
        "note": "Floors may rise and must never fall. precision = detections / (detections + "
                "false positives); recall = detections / (detections + misses), over "
                "evals/security/corpus.json.",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def negative(want) -> tuple[str, str]:
    """A must_not_detect entry: a bare category, or one with a severity floor."""
    if isinstance(want, str):
        return want, "LOW"
    return want["category"], want.get("min_severity", "LOW")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true", help="raise the floor to what the corpus holds now")
    args = parser.parse_args()
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    floors = read_floors()
    misses: list[str] = []
    false_positives: list[str] = []
    detected = 0

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        for case in corpus["cases"]:
            name = case["name"]
            findings = audit(materialise(case, root))

            for want in case.get("must_detect", []):
                floor = RANK[want.get("min_severity", "LOW")]
                hit = [
                    f for f in findings
                    if f["category"] == want["category"]
                    and RANK[f["severity"]] >= floor
                    and (want.get("in_file") is None or f["file"].endswith(want["in_file"]))
                ]
                if hit:
                    detected += 1
                else:
                    where = f" in {want['in_file']}" if want.get("in_file") else ""
                    misses.append(
                        f"{name}: missed {want['category']} "
                        f">= {want.get('min_severity', 'LOW')}{where} "
                        f"-- {case['description']}"
                    )

            for want in case.get("must_not_detect", []):
                category, severity = negative(want)
                noise = [f for f in findings if f["category"] == category and RANK[f["severity"]] >= RANK[severity]]
                if noise:
                    bound = f" >= {severity}" if severity != "LOW" else ""
                    false_positives.append(f"{name}: false positive {category}{bound}: {noise[0]['message']}")

    # Precision and recall over the corpus's expectations: a detection is a
    # satisfied must_detect, a miss an unsatisfied one, a false positive a
    # violated must_not_detect. The floor is what the gate holds, so a case
    # written ahead of its rule is a warning until the floor rises over it.
    precision = detected / (detected + len(false_positives)) if detected or false_positives else 1.0
    recall = detected / (detected + len(misses)) if detected or misses else 1.0
    below = [
        f"FAIL: {metric} {value:.3f} is below the floor {floors[metric]:.3f}"
        for metric, value in (("precision", precision), ("recall", recall))
        if value < floors[metric]
    ]
    level = "FAIL" if below else "WARN"
    for line in [*misses, *false_positives]:
        print(f"{level}: {line}")
    print(
        f"precision {precision:.3f} ({detected}/{detected + len(false_positives)}), "
        f"recall {recall:.3f} ({detected}/{detected + len(misses)}) "
        f"over {len(corpus['cases'])} case(s)"
    )
    if below:
        for line in below:
            print(line)
        print()
        print(f"FAIL: {len(misses) + len(false_positives)} security conformance issue(s) across {len(corpus['cases'])} case(s)")
        return 1
    if args.update:
        raised = {"precision": max(floors["precision"], precision), "recall": max(floors["recall"], recall)}
        if raised != floors:
            write_floors(raised)
            print(f"raised the floor to precision {raised['precision']:.3f}, recall {raised['recall']:.3f}")
    if misses or false_positives:
        print(f"OK: security corpus holds its floor -- {len(corpus['cases'])} case(s), {detected} detection(s), "
              f"{len(misses)} miss(es), {len(false_positives)} false positive(s)")
    else:
        print(f"OK: security corpus passed -- {len(corpus['cases'])} case(s), {detected} detection(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
