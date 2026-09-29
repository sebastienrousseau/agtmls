#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate scaffold templates."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"


REQUIRED = ["README.md", "skill/SKILL.md", "skill/reference.md", "skill/metadata.json", "evals/routing.json", "evals/behavioral.json"]
JSON_TEMPLATES = ["skill/metadata.json", "evals/routing.json", "evals/behavioral.json"]


def skill_template_problems() -> list[str]:
    """The skill template opens with frontmatter and carries the placeholder name."""
    path = TEMPLATES / "skill" / "SKILL.md"
    try:
        skill = path.read_text(encoding="utf-8") if path.exists() else ""
    except UnicodeDecodeError:
        return [f"{path.relative_to(ROOT)} is not UTF-8 text"]
    errors = [] if re.match(r"^---[ \t]*\n", skill) else ["skill template must start with frontmatter"]
    if "example-skill" not in skill:
        errors.append("skill template must contain example-skill placeholder")
    return errors


def json_problems() -> list[str]:
    errors = []
    for path in (TEMPLATES / rel for rel in JSON_TEMPLATES):
        if path.exists():
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                errors.append(f"{path.relative_to(ROOT)} is not UTF-8 text")
            except json.JSONDecodeError as exc:
                errors.append(f"{path.relative_to(ROOT)} invalid JSON: {exc}")
    return errors


def main() -> int:
    errors = [f"missing template: {(TEMPLATES / rel).relative_to(ROOT)}" for rel in REQUIRED if not (TEMPLATES / rel).exists()]
    errors += skill_template_problems() + json_problems()
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} template issue(s)")
        return 1
    print("OK: templates valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
