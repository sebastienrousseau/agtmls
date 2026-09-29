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
#
# The prose now says "every check in checks.json" instead of a number, so a
# new check edits nothing here. The scan stays to catch a number creeping
# back. The list is explicit because scanning every file flags skill content
# and test fixtures; it grew when a stale "57-gate" was found in the  check-count:historical
# shipped manpage and the pull request template, neither of which was listed.
COUNTED = [
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/conformance.yml",
    "AGENTS.md",
    "BENCHMARKS.md",
    "CONTRIBUTING.md",
    "DEVELOPMENT.md",
    "Makefile",
    "README.md",
    "docs/ECOSYSTEM.md",
    "docs/checks.md",
    "scripts/bench.py",
    "scripts/generate-manpage.py",
    "scripts/run-coverage.py",
    "scripts/run-unit-tests.py",
    "share/man/man1/agtmls.1",
]
# Any number of digits: limited to two or three, a gate of fewer than ten
# checks had every stated count go unread.
COUNT_CLAIM = re.compile(
    r"\b(\d+)[- ](?:check|gate)(?:s)?\b"
    r"|\ball (\d+) CI validation gates\b"
    r"|\brepository has (\d+) validation gates\b"
    r"|\bGate: \*\*(\d+) checks\*\*"
)
# A workflow step that runs a check: `run: python3 scripts/<script> <args>`.
RUN_STEP = re.compile(r"^\s*(?:-\s*)?run:\s*python3\s+scripts/(\S.*?)\s*$", re.MULTILINE)
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
    targets = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(node, ast.AnnAssign):  # `CHECKS: list[str] = [...]`
            targets.append(node.target)
    return sorted(
        target.id
        for target in targets
        if isinstance(target, ast.Name) and target.id in {"CHECKS", "COMPILE"}
    )


def workflow_commands(workflow: str) -> set[str]:
    """Each `run: python3 scripts/...` step, as `<script> <args>`.

    Searching the file for `scripts/<name>` counted a comment, or a step
    running the script with other arguments, as CI running the check.
    """
    return {" ".join(match.group(1).split()) for match in RUN_STEP.finditer(workflow)}


def runner_problems() -> list[str]:
    """run-all-checks.py reads checks.json and holds no list of its own."""
    try:
        names = redeclared_lists(RUNNER)
    except SyntaxError as exc:
        names, errors = [], [f"run-all-checks.py does not parse: {exc.msg} (line {exc.lineno})"]
    else:
        errors = []
    errors += [f"run-all-checks.py re-declares the gate as {name}; it must read checks.json" for name in names]
    if "checks.json" not in RUNNER.read_text(encoding="utf-8"):
        errors.append("run-all-checks.py never reads checks.json")
    return errors


def count_problems(manifest: list) -> list[str]:
    """Every count stated in a counted document equals the manifest's."""
    errors = []
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
    return errors


def ci_problems(manifest: list) -> list[str]:
    """Each manifest check has its script, and is a step in the workflow."""
    workflow = WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.exists() else ""
    errors = [] if workflow else [f"CI workflow missing: {WORKFLOW.relative_to(ROOT)}"]
    commands = workflow_commands(workflow)
    for check in manifest:
        script = check.split()[0]
        if not (ROOT / "scripts" / script).exists():
            errors.append(f"manifest check script missing: {script}")
        # Local-only checks are not a gate. Every manifest entry must also be
        # a step in the workflow, or CI is weaker than `agtmls check`.
        if workflow and " ".join(check.split()) not in commands:
            errors.append(f"check not run by validate.yml: {check}")
    return errors


def load_manifest() -> dict | str:
    """checks.json, or why it cannot be read as an object."""
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"checks.json is not valid JSON: {exc}"
    return data if isinstance(data, dict) else "checks.json must be a JSON object"


def manifest_checks(checks: object) -> tuple[list[str], list[str]]:
    """(the command strings the manifest lists, what is wrong with the list)."""
    if not isinstance(checks, list):
        return [], ["checks.json checks must be a list of command strings"]
    valid = [check for check in checks if isinstance(check, str) and check.split()]
    errors = [
        f"checks.json entry {index} must be a non-empty command string"
        for index, check in enumerate(checks) if not (isinstance(check, str) and check.split())
    ]
    return valid, errors


def main() -> int:
    data = load_manifest()
    if isinstance(data, str):
        print(f"FAIL: {data}")
        return 1
    manifest, errors = manifest_checks(data.get("checks", []))

    if data.get("schema_version") != 1:
        errors.append("checks.json schema_version must be 1")
    errors += runner_problems() + count_problems(manifest) + ci_problems(manifest)

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
