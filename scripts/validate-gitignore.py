#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
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


def patterns(text: str) -> list[str]:
    """The .gitignore's patterns, blank lines and comments dropped."""
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def policy_problems(lines: list[str]) -> list[str]:
    """Required patterns that are missing, and patterns listed twice."""
    errors = [f"missing required .gitignore pattern: {pattern}" for pattern in REQUIRED if pattern not in lines]
    errors += [f"duplicate .gitignore pattern: {pattern}" for pattern in sorted({line for line in lines if lines.count(line) > 1})]
    return errors


def read_policy() -> str | list[str]:
    """The .gitignore's text, or the problem that stops it being read."""
    try:
        return GITIGNORE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [".gitignore is missing"]
    except UnicodeDecodeError:
        return [".gitignore is not UTF-8 text"]


def main() -> int:
    text = read_policy()
    errors = text if isinstance(text, list) else policy_problems(patterns(text))
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
