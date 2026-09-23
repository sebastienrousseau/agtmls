#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Hold README.md to the portfolio README template.

The template (README-TEMPLATE.md at the portfolio root) fixes the section
headings and their order, and requires that no `{{VARIABLE}}` survive into a
committed README. The portfolio audit checks this across every repository;
this is the same check, in the repository's own gate, so a pull request
learns about a missing section before the audit does. The rules below mirror
the audit's `readme_template_status` and must move with it.

    python3 scripts/validate-readme.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

HEADINGS = [
    "Contents",
    "Install",
    "Requirements",
    "Quick Start",
    "The {project} ecosystem",
    "Capabilities at a glance",
    "Ecosystem comparison",
    "Benchmarks",
    "Features",
    "Configuration",
    "Examples",
    "When not to use {project}",
    "Development",
    "Security",
    "Documentation",
    "Stability guarantees",
    "License",
]
STRUCTURE = [
    "<!-- SPDX-License-Identifier:",
    '<p align="center">',
    '<h1 align="center">',
    "ossf-scorecard",
]
TITLE = re.compile(r'<h1 align="center">([^<]+)</h1>')
H2 = re.compile(r"(?m)^## ([^\n]+)$")


def problems(text: str) -> list[str]:
    if "{{" in text or "}}" in text:
        return ["unresolved template variables"]
    title = TITLE.search(text)
    if not title:
        return ["centered project h1 missing"]
    project = title.group(1).strip()
    required = [heading.format(project=project) for heading in HEADINGS]
    actual = H2.findall(text)
    found: list[str] = []
    if actual != required:
        found += [f"missing heading: {h}" for h in required if h not in actual]
        found += [f"unexpected heading: {h}" for h in actual if h not in required]
        if not found:
            found.append("required headings are out of order")
    found += [f"missing structure: {signal}" for signal in STRUCTURE if signal not in text]
    return found


def main() -> int:
    if not README.is_file():
        print("FAIL: README.md is missing")
        return 1
    found = problems(README.read_text(encoding="utf-8"))
    for problem in found:
        print(f"FAIL: README.md: {problem}")
    if found:
        print("See README-TEMPLATE.md at the portfolio root for the required layout.")
        return 1
    print(f"OK: README.md follows the template ({len(HEADINGS)} sections, in order)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
