#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate structure density and cache-friendly prefixes in context files.

Audits AGENTS.md and GEMINI.md: an estimated token budget, an instruction
density floor, and no timestamp in the first 50 lines. The system prompts
are checked for volatile text by validate-system-prompts.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _lib.context_optimizer import (  # noqa: E402
    estimate_tokens,
    findings,
    structured_line_density,
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

    density = structured_line_density(text)
    if density < MIN_DENSITY:
        issues.append(f"{path.name} density too low: {density} list/table lines per 100 tokens (< {MIN_DENSITY})")

    issues += [f"{path.name}:{note}" for note in findings(text) if "timestamp" in note]

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
