#!/usr/bin/env python3
"""Validate checks.json against run-all-checks.py AND the CI workflow.

Three places must agree on the gate: the manifest, the local runner, and
`.github/workflows/validate.yml`. The workflow enumerates each check as its
own step, so a check added to the manifest and the runner can still silently
miss CI — which is exactly what happened to validate-packaging.py,
sync-skill-frontmatter.py, and generate-plugin-manifests.py. A green local
gate then means nothing about a pull request.
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


def runner_checks() -> list[str]:
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "CHECKS":
                    checks: list[str] = []
                    for item in ast.literal_eval(node.value):
                        checks.append(" ".join(item))
                    return checks
    return []


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = data.get("checks", [])
    runner = runner_checks()
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("checks.json schema_version must be 1")
    if manifest != runner:
        errors.append("checks.json does not match run-all-checks.py CHECKS order")
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
