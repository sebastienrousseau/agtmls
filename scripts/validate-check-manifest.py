#!/usr/bin/env python3
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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "checks.json"
RUNNER = ROOT / "scripts" / "run-all-checks.py"
WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"


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
