#!/usr/bin/env python3
"""Run release-focused AgtMLS checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKS = [
    ["validate-plugin-manifest.py"],
    ["validate-providers.py"],
    ["validate-profiles.py"],
    ["validate-release.py"],
    ["generate-skill-index.py", "--check"],
    ["generate-catalog.py", "--check"],
    ["generate-docs-site.py", "--check"],
    ["generate-agent-card.py", "--check"],
    ["generate-mcp-resources.py", "--check"],
    ["generate-sbom.py", "--check"],
    ["generate-provenance.py", "--check"],
    ["validate-generated-artifacts.py"],
    ["validate-check-manifest.py"],
]


def main() -> int:
    for check in CHECKS:
        cmd = [sys.executable, str(ROOT / "scripts" / check[0]), *check[1:]]
        print(f"$ {' '.join(cmd)}")
        rc = subprocess.call(cmd, cwd=ROOT)
        if rc != 0:
            return rc
    print("OK: release check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
