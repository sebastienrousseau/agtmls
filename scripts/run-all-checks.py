#!/usr/bin/env python3
"""Run the full AgtMLS local validation gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKS = [
    ["validate-skills.py"],
    ["validate-commands.py"],
    ["validate-plugin-manifest.py"],
    ["validate-providers.py"],
    ["validate-profiles.py"],
    ["validate-templates.py"],
    ["validate-doc-links.py"],
    ["validate-json-files.py"],
    ["validate-python-scripts.py"],
    ["validate-shell-syntax.py"],
    ["validate-secrets.py"],
    ["validate-gitignore.py"],
    ["validate-cli-surface.py"],
    ["validate-system-prompts.py"],
    ["check-skill-collisions.py"],
    ["validate-eval-cases.py"],
    ["run-trigger-evals.py"],
    ["run-behavioral-evals.py"],
    ["validate-skill-metadata.py"],
    ["generate-skill-index.py", "--check"],
    ["generate-catalog.py", "--check"],
    ["validate-generated-artifacts.py"],
    ["validate-skill-index.py"],
    ["validate-lifecycle.py"],
    ["validate-release.py"],
    ["release-check.py"],
    ["smoke-install.py"],
    ["smoke-cli.py"],
    ["smoke-export.py"],
    ["smoke-import.py"],
    ["smoke-proposal.py"],
    ["smoke-scaffold.py"],
    ["run-unit-tests.py"],
    ["validate-check-manifest.py"],
    ["agtmls-doctor.py"],
]
COMPILE = [
    "agtmls.py",
    "agtmls-doctor.py",
    "export-registry.py",
    "generate-catalog.py",
    "generate-skill-index.py",
    "import-skill.py",
    "propose-skill-from-session.py",
    "registry-diff.py",
    "release-check.py",
    "run-behavioral-evals.py",
    "run-all-checks.py",
    "run-unit-tests.py",
    "scaffold-skill.py",
    "smoke-cli.py",
    "smoke-export.py",
    "smoke-import.py",
    "smoke-install.py",
    "smoke-proposal.py",
    "smoke-scaffold.py",
    "validate-check-manifest.py",
    "validate-cli-surface.py",
    "validate-commands.py",
    "validate-doc-links.py",
    "validate-eval-cases.py",
    "validate-generated-artifacts.py",
    "validate-gitignore.py",
    "validate-json-files.py",
    "validate-lifecycle.py",
    "validate-plugin-manifest.py",
    "validate-profiles.py",
    "validate-providers.py",
    "validate-python-scripts.py",
    "validate-release.py",
    "validate-secrets.py",
    "validate-shell-syntax.py",
    "validate-skill-index.py",
    "validate-skill-metadata.py",
    "validate-system-prompts.py",
    "validate-templates.py",
]


def main() -> int:
    for check in CHECKS:
        cmd = [sys.executable, str(ROOT / "scripts" / check[0]), *check[1:]]
        print(f"$ {' '.join(cmd)}")
        rc = subprocess.call(cmd, cwd=ROOT)
        if rc != 0:
            return rc
    cmd = [sys.executable, "-m", "py_compile", *[str(ROOT / "scripts" / script) for script in COMPILE]]
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
