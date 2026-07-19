#!/usr/bin/env python3
"""Validate AgtMLS system prompt profiles."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "system-prompts"
LANGUAGES = ["rust", "python", "go", "cpp", "swift", "typescript", "javascript", "ruby", "bash"]


def main() -> int:
    errors: list[str] = []
    base = PROMPTS / "_base.md"
    if not base.exists():
        errors.append("system-prompts/_base.md missing")
    elif "# " not in base.read_text(encoding="utf-8"):
        errors.append("system-prompts/_base.md missing top-level heading")
    for lang in LANGUAGES:
        path = PROMPTS / f"{lang}.md"
        if not path.exists():
            errors.append(f"system-prompts/{lang}.md missing")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"system-prompts/{lang}.md is empty")
        if "# " not in text:
            errors.append(f"system-prompts/{lang}.md missing top-level heading")
    extras = sorted(
        p.name for p in PROMPTS.glob("*.md")
        if p.stem not in set(LANGUAGES) | {"_base"}
    )
    if extras:
        errors.append(f"unexpected system prompt profile(s): {', '.join(extras)}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} system prompt issue(s)")
        return 1
    print(f"OK: {len(LANGUAGES)} language profile(s) plus base prompt valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
