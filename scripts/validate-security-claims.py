#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Keep the security documentation to claims the code can back.

AgtMLS's analyzer is static and pattern-based. Self-extracting packing evades
every static skill scanner tested at over 90% (arXiv 2607.02357), so the
analyzer is first-stage triage, not a defence. The README nonetheless
promised "proactive defense" and listed "Attack Vectors Defended". A trust
product that overclaims is discredited by the first bypass, and the claim is
the part a reader remembers.

Two rules:

1. README.md, SECURITY.md and docs/ make no absolute security claim:
   no "defends against", "prevents attacks", "guarantees ... safe",
   "immune", "detects all malicious".
2. SECURITY.md keeps a "Boundaries and heuristics" section that says which
   protections are structural and which are best-effort.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECURITY = ROOT / "SECURITY.md"
BOUNDARIES_HEADING = "## Boundaries and heuristics"

OVERCLAIMS = [
    re.compile(r"\bdefen[cs]es?\s+against\b", re.IGNORECASE),
    re.compile(r"\bdefend(?:s|ed)?\s+against\b", re.IGNORECASE),
    re.compile(r"\battack\s+vectors?\s+defended\b", re.IGNORECASE),
    re.compile(r"\bprevents?\s+(?:all\s+)?(?:malicious|attacks?|prompt\s+injection|injection|exfiltration)\b", re.IGNORECASE),
    re.compile(r"\bguarantee(?:s|d)?\b[^.\n]{0,60}\b(?:malicious|safe|secure|attacks?|injection)\b", re.IGNORECASE),
    re.compile(r"\b(?:immune|bulletproof|unbypassable)\b", re.IGNORECASE),
    re.compile(r"\b(?:detects?|blocks?|stops?|catches)\s+(?:all|every|any)\s+(?:malicious|attacks?)", re.IGNORECASE),
]


def documents() -> list[Path]:
    found = [ROOT / "README.md", SECURITY]
    found += sorted((ROOT / "docs").rglob("*.md"))
    return [path for path in found if path.is_file()]


def main() -> int:
    errors: list[str] = []
    for path in documents():
        rel = path.relative_to(ROOT)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern in OVERCLAIMS:
                match = pattern.search(line)
                if match:
                    errors.append(f"{rel}:{number}: absolute security claim {match.group(0)!r}")
    if not SECURITY.is_file() or BOUNDARIES_HEADING not in SECURITY.read_text(encoding="utf-8"):
        errors.append(f"SECURITY.md: missing '{BOUNDARIES_HEADING}' -- say what is structural and what is best-effort")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} security claim issue(s)")
        return 1
    print(f"OK: {len(documents())} document(s) claim only what the code backs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
