#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate instruction density and cache-friendly prefixes in context files.

Audits AGENTS.md, GEMINI.md, and system prompt markdown files to ensure
volatile timestamps are excluded from prefix lines and instruction density
meets threshold standards.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _lib.context_optimizer import (  # noqa: E402
    enforce_cache_friendly_prefix,
    estimate_tokens,
    instruction_density,
)

MIN_DENSITY = 0.5
MAX_TOKENS = 5000


def audit_file(path: Path) -> list[str]:
    """Audit a single markdown context file."""
    issues: list[str] = []
    if not path.exists():
        return issues
    text = path.read_text(encoding="utf-8")
    tokens = estimate_tokens(text)
    if tokens > MAX_TOKENS:
        issues.append(f"{path.name} exceeds max token budget ({tokens} > {MAX_TOKENS})")

    density = instruction_density(text)
    if density < MIN_DENSITY:
        issues.append(f"{path.name} instruction density too low ({density} < {MIN_DENSITY})")

    clean_prefix = enforce_cache_friendly_prefix(text)
    if clean_prefix != text:
        issues.append(f"{path.name} contains volatile timestamps in the top 50 lines")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    targets = (
        ROOT / "AGENTS.md",
        ROOT / "GEMINI.md",
    )

    all_issues: list[str] = []
    for target in targets:
        all_issues.extend(audit_file(target))

    if all_issues:
        for issue in all_issues:
            print(f"FAIL: {issue}")
        return 1

    print("OK: context files meet density standards and cache prefix invariants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
