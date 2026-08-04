#!/usr/bin/env python3
"""Every file must declare its licence, in the form its format allows.

REUSE-style headers are the norm, but two file classes cannot carry a leading
comment: `SKILL.md` and `commands/*.md` must begin with `---` at byte 0 or
their frontmatter stops parsing. Those declare `license:` inside the
frontmatter instead — the Agent Skills spec reserves the field for exactly
this. This check enforces whichever form applies, so "add a licence header"
can never silently break a skill.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPDX = "SPDX-License-Identifier"
# Directories that are not ours to header.
SKIP_DIRS = {".git", "dist", "__pycache__", ".ruff_cache", ".agtmls", "node_modules"}
FRONTMATTER_FIRST = {"SKILL.md"}
FRONTMATTER_DIRS = {"commands"}


def frontmatter_licence(text: str) -> bool:
    match = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    return bool(match) and bool(re.search(r"^license:[ \t]*\S", match.group(1), re.MULTILINE))


def wants_frontmatter(path: Path) -> bool:
    if path.name in FRONTMATTER_FIRST:
        return True
    # README.md inside commands/ documents the directory; it is not a command.
    if path.name == "README.md":
        return False
    rel = path.relative_to(ROOT)
    return len(rel.parts) > 1 and rel.parts[0] in FRONTMATTER_DIRS and path.suffix == ".md"


def main() -> int:
    errors: list[str] = []
    checked = 0
    for path in sorted(ROOT.rglob("*.md")):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        checked += 1
        text = path.read_text(encoding="utf-8")
        if wants_frontmatter(path):
            if not frontmatter_licence(text):
                errors.append(f"{rel}: must declare `license:` in frontmatter (no leading comment allowed)")
            elif text.lstrip().startswith("<!--"):
                errors.append(f"{rel}: frontmatter must start at byte 0; move the licence into `license:`")
        elif SPDX not in text:
            errors.append(f"{rel}: missing an {SPDX} header")

    for suffix in (".py", ".sh"):
        for path in sorted(ROOT.rglob(f"*{suffix}")):
            rel = path.relative_to(ROOT)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            checked += 1

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} licence header issue(s)")
        return 1
    print(f"OK: licence declared for {checked} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
