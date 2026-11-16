#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Acceptance run of `audit --foreign` over real repositories.

evals/security/foreign-acceptance.json pins each repository the analyzer's
rules were built from to a commit and lists the rule IDs an audit of that
commit must report, and any provisional policy it must infer. Nothing from
those repositories is committed: their text is theirs, and the IDs are
enough to show a rule still fires where it was seen.

    python3 scripts/run-foreign-acceptance.py                  # clone each pinned commit
    python3 scripts/run-foreign-acceptance.py --clones DIR     # reuse DIR/<owner>_<repo> checkouts

A reused checkout must be at the pinned commit. Reporting more rules than
listed passes (a new rule may find more); missing one fails.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "scripts" / "audit-skill.py"
ACCEPTANCE = ROOT / "evals" / "security" / "foreign-acceptance.json"


def target(entry: dict, clones: Path | None) -> str:
    """A local checkout at the pinned commit, or `<url>@<commit>` to clone."""
    if clones is not None:
        return str(clones / entry["repo"].replace("/", "_"))
    return f"https://github.com/{entry['repo']}.git@{entry['commit']}"


def head(checkout: str) -> str | None:
    proc = subprocess.run(["git", "-C", checkout, "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def audit(where: str) -> dict | str:
    """The foreign audit's JSON report, or why there is none."""
    proc = subprocess.run([sys.executable, str(AUDIT), "--foreign", where, "--format", "json"],
                          capture_output=True, text=True, check=False)
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return f"no report (exit {proc.returncode}): {proc.stderr.strip()[:200]}"


def reported(report: dict) -> set[str]:
    config = report.get("agent_config", {})
    findings = [f for s in report["skills"] for f in s["findings"] + s["suppressed"]]
    findings += config.get("findings", []) + config.get("suppressed", [])
    return {f["rule"] for f in findings}


def check(entry: dict, report: dict) -> list[str]:
    """What the report misses: an expected rule, or an expected policy value."""
    problems = [f"{entry['repo']}: {rule} not reported" for rule in sorted(set(entry["rules"]) - reported(report))]
    policies = {s["path"]: s["policy"] for s in report["skills"]}
    for path, expected in sorted(entry.get("policy", {}).items()):
        actual = policies.get(path, {})
        problems += [f"{entry['repo']}: {path} {key} is {actual.get(key)!r}, expected {value!r}"
                     for key, value in sorted(expected.items()) if actual.get(key) != value]
    return problems


def run_one(entry: dict, clones: Path | None) -> list[str]:
    where = target(entry, clones)
    if clones is not None and head(where) != entry["commit"]:
        return [f"{entry['repo']}: {where} is not a checkout of {entry['commit']}"]
    report = audit(where)
    if isinstance(report, str):
        return [f"{entry['repo']}: {report}"]
    return check(entry, report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--clones", type=Path, help="reuse checkouts named <owner>_<repo> in this directory")
    parser.add_argument("--acceptance", type=Path, default=ACCEPTANCE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    entries = json.loads(args.acceptance.read_text(encoding="utf-8"))["repos"]
    problems: list[str] = []
    for entry in entries:
        found = run_one(entry, args.clones)
        print(f"{'FAIL' if found else 'OK'}: {entry['repo']} @ {entry['commit'][:12]} ({len(entry['rules'])} rule(s))")
        problems += found
    for problem in problems:
        print(f"  {problem}")
    print(f"{len(entries) - len({p.split(':', 1)[0] for p in problems})}/{len(entries)} repositories as expected")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
