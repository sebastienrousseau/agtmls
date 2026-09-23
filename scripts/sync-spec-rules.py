#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Snapshot agtmls-spec/rules/*.toml into scripts/_lib/rules.json.

The normative rule set lives in agtmls-spec, one TOML file per rule.
agtmls-core loads those files directly; this repository used to restate
every pattern by hand in rules.py, and drift was caught only by a
differential run in other repositories' CI.

Now rules.py builds its tables from rules.json, and this script is the only
thing that writes rules.json:

    # refresh from a spec checkout (needs Python 3.11+ for tomllib)
    python3 scripts/sync-spec-rules.py --write --from ../agtmls-spec

    # gate: the snapshot is self-consistent (any supported Python)
    python3 scripts/sync-spec-rules.py --check

    # CI: the snapshot is exactly what the pinned spec commit says
    python3 scripts/sync-spec-rules.py --check --from path/to/agtmls-spec

"Self-consistent" means what the spec's own loader requires: every pattern
compiles, matches each of its `true_positive` examples and none of its
`false_positive` ones. The examples travel inside the snapshot, so the check
needs no TOML parser and runs on 3.10.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "scripts" / "_lib" / "rules.json"
REPOSITORY = "sebastienrousseau/agtmls-spec"


def load_spec(spec: Path, commit: str | None) -> dict:
    """Read every rule file from a spec checkout into snapshot form."""
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - exercised only on 3.10
        raise SystemExit("FAIL: reading the spec needs tomllib (Python 3.11+)") from None

    files = sorted((spec / "rules").glob("AGT-*.toml"))
    if not files:
        raise SystemExit(f"FAIL: no AGT-*.toml rule files under {spec / 'rules'}")
    if commit is None:
        commit = subprocess.run(
            ["git", "-C", str(spec), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    rules = [tomllib.loads(path.read_text(encoding="utf-8")) for path in files]
    return {
        "source": {
            "repository": REPOSITORY,
            "commit": commit,
            "files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        },
        "rules": sorted(rules, key=lambda rule: rule["id"]),
    }


def problems(snapshot: dict) -> list[str]:
    """Everything the spec's own loader would refuse."""
    errors: list[str] = []
    ids = [rule.get("id") for rule in snapshot.get("rules", [])]
    if len(ids) != len(set(ids)):
        errors.append("rule ids are not unique")
    if ids != sorted(ids):
        errors.append("rules are not sorted by id")
    if "AGT-STEG-001" not in ids:
        errors.append("AGT-STEG-001 (the invisible code point list) is missing")
    for rule in snapshot.get("rules", []):
        rule_id = rule.get("id", "?")
        for key in ("category", "severity", "title", "description"):
            if not rule.get(key):
                errors.append(f"{rule_id}: missing {key}")
        if "pattern" not in rule:
            continue
        try:
            regex = re.compile(rule["pattern"])
        except re.error as exc:
            errors.append(f"{rule_id}: pattern does not compile: {exc}")
            continue
        for example in rule.get("true_positive", []):
            if not regex.search(example["text"]):
                errors.append(f"{rule_id}: misses its own true positive {example['text']!r}")
        for example in rule.get("false_positive", []):
            if regex.search(example["text"]):
                errors.append(f"{rule_id}: matches its own false positive {example['text']!r}")
    return errors


def drift(snapshot: dict, spec: dict) -> list[str]:
    """Rule ids whose definition differs between the snapshot and the spec."""
    ours = {rule["id"]: rule for rule in snapshot.get("rules", [])}
    theirs = {rule["id"]: rule for rule in spec["rules"]}
    return [
        f"{rule_id}: snapshot and spec disagree"
        for rule_id in sorted(set(ours) | set(theirs))
        if ours.get(rule_id) != theirs.get(rule_id)
    ]


def render(snapshot: dict) -> str:
    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="spec", type=Path, help="an agtmls-spec checkout")
    parser.add_argument("--commit", help="record this commit instead of asking git (for a copy)")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.write:
        if args.spec is None:
            parser.error("--write needs --from <agtmls-spec checkout>")
        snapshot = load_spec(args.spec, args.commit)
        errors = problems(snapshot)
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            return 1
        SNAPSHOT.write_text(render(snapshot), encoding="utf-8")
        print(f"wrote {SNAPSHOT.relative_to(ROOT)} ({len(snapshot['rules'])} rules at {snapshot['source']['commit'][:12]})")
        return 0

    if args.check:
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        errors = problems(snapshot)
        if args.spec is not None:
            errors += drift(snapshot, load_spec(args.spec, args.commit))
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            print()
            print(f"FAIL: {len(errors)} rule snapshot issue(s)")
            return 1
        where = f" and matches {args.spec}" if args.spec else ""
        print(f"OK: {len(snapshot['rules'])} rules, self-consistent{where}")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
