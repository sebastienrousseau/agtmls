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
    ["generate-docs-site.py", "--check"],
    ["generate-agent-card.py", "--check"],
    ["generate-mcp-resources.py", "--check"],
    ["generate-sbom.py", "--check"],
    ["generate-provenance.py", "--check"],
    ["validate-generated-artifacts.py"],
    ["validate-docs-site.py"],
    ["validate-governance.py"],
    ["validate-skill-index.py"],
    ["validate-lifecycle.py"],
    ["validate-version-policy.py"],
    ["validate-release.py"],
    ["release-check.py"],
    ["smoke-release-pack.py"],
    ["smoke-next-version.py"],
    ["smoke-release-dry-run.py"],
    ["smoke-evolve-evidence.py"],
    ["smoke-provider-install.py"],
    ["smoke-install.py"],
    ["smoke-install-profiles.py"],
    ["smoke-cli.py"],
    ["smoke-export.py"],
    ["smoke-import.py"],
    ["smoke-proposal.py"],
    ["smoke-scaffold.py"],
    ["run-unit-tests.py"],
    ["bench.py"],
    ["validate-check-manifest.py"],
    ["agtmls-doctor.py"],
]
COMPILE = [
    "agtmls-doctor.py",
    "agtmls.py",
    "bench.py",
    "check-skill-collisions.py",
    "evolve-session.py",
    "export-registry.py",
    "generate-agent-card.py",
    "generate-catalog.py",
    "generate-docs-site.py",
    "generate-mcp-resources.py",
    "generate-provenance.py",
    "generate-sbom.py",
    "generate-skill-index.py",
    "import-skill.py",
    "verify-release-assets.py",
    "smoke-release-dry-run.py",
    "smoke-next-version.py",
    "release-dry-run.py",
    "next-version.py",
    "propose-skill-from-session.py",
    "provider-install.py",
    "record-evidence.py",
    "registry-diff.py",
    "release-check.py",
    "release-pack.py",
    "run-all-checks.py",
    "run-behavioral-evals.py",
    "run-trigger-evals.py",
    "run-unit-tests.py",
    "scaffold-skill.py",
    "smoke-cli.py",
    "smoke-evolve-evidence.py",
    "smoke-export.py",
    "smoke-import.py",
    "smoke-install-profiles.py",
    "smoke-install.py",
    "smoke-proposal.py",
    "smoke-provider-install.py",
    "smoke-release-pack.py",
    "smoke-scaffold.py",
    "validate-check-manifest.py",
    "validate-cli-surface.py",
    "validate-commands.py",
    "validate-doc-links.py",
    "validate-docs-site.py",
    "validate-eval-cases.py",
    "validate-generated-artifacts.py",
    "validate-gitignore.py",
    "validate-governance.py",
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
    "validate-skills.py",
    "validate-system-prompts.py",
    "validate-templates.py",
    "validate-version-policy.py",
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
