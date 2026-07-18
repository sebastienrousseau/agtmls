#!/usr/bin/env python3
"""Scan repository text files for likely committed secrets."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__"}
TEXT_SUFFIXES = {".md", ".py", ".sh", ".json", ".yml", ".yaml", ".toml", ".txt"}
PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9._/\-+=]{20,}"),
    re.compile(r"\b(?:sk|ghp|gho|github_pat)_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
]


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {".gitignore"}:
            files.append(path)
    return sorted(files)


def main() -> int:
    errors: list[str] = []
    for path in iter_text_files():
        if path.name == "validate-secrets.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in PATTERNS:
                if pattern.search(line):
                    errors.append(f"{path.relative_to(ROOT)}:{lineno}: likely secret")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} likely secret(s)")
        return 1
    print(f"OK: no likely secrets in {len(iter_text_files())} text file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
