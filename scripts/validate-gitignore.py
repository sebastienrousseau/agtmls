#!/usr/bin/env python3
"""Validate repository ignore policy for generated local artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITIGNORE = ROOT / ".gitignore"
REQUIRED = [
    ".DS_Store",
    "*.swp",
    "*.swo",
    "*~",
    ".ruff_cache/",
    "__pycache__/",
    ".agtmls/",
]


def main() -> int:
    lines = [
        line.strip()
        for line in GITIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    missing = [pattern for pattern in REQUIRED if pattern not in lines]
    duplicates = sorted({line for line in lines if lines.count(line) > 1})
    errors: list[str] = []
    for pattern in missing:
        errors.append(f"missing required .gitignore pattern: {pattern}")
    for pattern in duplicates:
        errors.append(f"duplicate .gitignore pattern: {pattern}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} .gitignore policy issue(s)")
        return 1
    print(f"OK: .gitignore policy valid with {len(REQUIRED)} required pattern(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
