#!/usr/bin/env python3
"""Validate local Markdown links."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SKIP_DIRS = {".git", "__pycache__"}


def iter_markdown() -> list[Path]:
    paths = []
    for path in ROOT.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        paths.append(path)
    return sorted(paths)


def local_target(raw: str) -> str | None:
    target = raw.strip()
    if not target or target.startswith("#"):
        return None
    if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
        return None
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target.split("#", 1)[0]


def main() -> int:
    errors: list[str] = []
    files = iter_markdown()
    for md in files:
        text = md.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            target = local_target(match.group(1))
            if target is None:
                continue
            resolved = (md.parent / target).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                errors.append(f"{md.relative_to(ROOT)}: link escapes repo: {match.group(1)}")
                continue
            if not resolved.exists():
                errors.append(f"{md.relative_to(ROOT)}: missing local link target: {match.group(1)}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} broken local markdown link(s)")
        return 1
    print(f"OK: local markdown links valid across {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
