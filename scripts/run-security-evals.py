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


def main() -> int:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    errors: list[str] = []
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
                    errors.append(
                        f"{name}: missed {want['category']} "
                        f">= {want.get('min_severity', 'LOW')}{where} "
                        f"-- {case['description']}"
                    )

            for category in case.get("must_not_detect", []):
                noise = [f for f in findings if f["category"] == category]
                if noise:
                    errors.append(f"{name}: false positive {category}: {noise[0]['message']}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} security conformance issue(s) across {len(corpus['cases'])} case(s)")
        return 1
    print(f"OK: security corpus passed -- {len(corpus['cases'])} case(s), {detected} detection(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
