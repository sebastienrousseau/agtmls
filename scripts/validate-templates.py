#!/usr/bin/env python3
"""Validate scaffold templates."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"


def main() -> int:
    errors: list[str] = []
    required = [
        TEMPLATES / "README.md",
        TEMPLATES / "skill" / "SKILL.md",
        TEMPLATES / "skill" / "reference.md",
        TEMPLATES / "skill" / "metadata.json",
        TEMPLATES / "evals" / "routing.json",
        TEMPLATES / "evals" / "behavioral.json",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing template: {path.relative_to(ROOT)}")
    skill = (TEMPLATES / "skill" / "SKILL.md").read_text(encoding="utf-8") if (TEMPLATES / "skill" / "SKILL.md").exists() else ""
    if not re.match(r"^---[ \t]*\n", skill):
        errors.append("skill template must start with frontmatter")
    if "example-skill" not in skill:
        errors.append("skill template must contain example-skill placeholder")
    for path in [
        TEMPLATES / "skill" / "metadata.json",
        TEMPLATES / "evals" / "routing.json",
        TEMPLATES / "evals" / "behavioral.json",
    ]:
        if path.exists():
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"{path.relative_to(ROOT)} invalid JSON: {exc}")
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
