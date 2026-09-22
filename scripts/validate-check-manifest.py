#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate checks.json against the CI workflow, and keep it the only copy.

Two places must agree on the gate: the manifest and
`.github/workflows/validate.yml`. The workflow enumerates each check as its
own step, so a check added to the manifest can still silently miss CI — which
is exactly what happened to validate-packaging.py, sync-skill-frontmatter.py
and generate-plugin-manifests.py. A green local gate then means nothing about
a pull request.

The local runner used to be a third place, holding a hand-copied list, and
this check compared the two. It no longer holds one: `run-all-checks.py`
reads `checks.json`. What is enforced here instead is that it stays that way,
because a re-declared list is how the drift starts.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "checks.json"
RUNNER = ROOT / "scripts" / "run-all-checks.py"
WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"

# Prose that states how many checks there are. The number was 57 in AGENTS.md,
# 62 in the Makefile and 62 in docs/ECOSYSTEM.md while the manifest held 62,
# and a later edit left four more "57-gate" claims in README.md that a  check-count:historical
# search
# for the other spellings did not find. A count repeated in a dozen files is a
# claim nobody is enforcing, which is exactly what criterion 5.9 is about.
COUNTED = [
    "AGENTS.md",
    "CONTRIBUTING.md",
    "DEVELOPMENT.md",
    "Makefile",
    "README.md",
    "docs/ECOSYSTEM.md",
    "scripts/run-unit-tests.py",
]
COUNT_CLAIM = re.compile(
    r"\b(\d{2,3})[- ](?:check|gate)(?:s)?\b"
    r"|\ball (\d{2,3}) CI validation gates\b"
    r"|\brepository has (\d{2,3}) validation gates\b"
    r"|\bGate: \*\*(\d{2,3}) checks\*\*"
)
# Prose that cites a past count on purpose -- a changelog line, or a comment
# explaining why this check exists -- marks the line. An exemption has to be
# visible and greppable; the alternative is writers contorting sentences to
# get past a regex, which is how a check stops meaning anything.
HISTORICAL = "check-count:historical"


def count_claims(text: str) -> list[tuple[int, int]]:
    """(claimed count, 1-based line number) for every unexempted claim."""
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        if HISTORICAL in line:
            continue
        for match in COUNT_CLAIM.finditer(line):
            found.append((int(next(g for g in match.groups() if g)), number))
    return found


def redeclared_lists(runner: Path) -> list[str]:
    """Module-level names in the runner that would shadow the manifest."""
    tree = ast.parse(runner.read_text(encoding="utf-8"))
    return sorted(
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id in {"CHECKS", "COMPILE"}
    )


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = data.get("checks", [])
    errors: list[str] = []

    if data.get("schema_version") != 1:
        errors.append("checks.json schema_version must be 1")

    for name in redeclared_lists(RUNNER):
        errors.append(
            f"run-all-checks.py re-declares the gate as {name}; it must read checks.json"
        )
    if "checks.json" not in RUNNER.read_text(encoding="utf-8"):
        errors.append("run-all-checks.py never reads checks.json")

    for relative in COUNTED:
        path = ROOT / relative
        if not path.exists():
            errors.append(f"counted document missing: {relative}")
            continue
        for number, line in count_claims(path.read_text(encoding="utf-8")):
            if number != len(manifest):
                errors.append(
                    f"{relative}:{line}: claims {number} checks; "
                    f"checks.json has {len(manifest)}"
                )

    workflow = WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.exists() else ""
    if not workflow:
        errors.append(f"CI workflow missing: {WORKFLOW.relative_to(ROOT)}")
    for check in manifest:
        script = check.split()[0]
        if not (ROOT / "scripts" / script).exists():
            errors.append(f"manifest check script missing: {script}")
        # Local-only checks are not a gate. Every manifest entry must also be
        # a step in the workflow, or CI is weaker than `agtmls check`.
        if workflow and f"scripts/{script}" not in workflow:
            errors.append(f"check not run by validate.yml: {check}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} check manifest issue(s)")
        return 1
    print(f"OK: check manifest valid with {len(manifest)} check(s), all present in CI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
