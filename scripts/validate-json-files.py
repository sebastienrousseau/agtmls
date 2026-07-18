#!/usr/bin/env python3
"""Validate JSON files and reject duplicate object keys."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__"}


def no_duplicates_object_pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key: {key}")
        out[key] = value
    return out


def iter_json() -> list[Path]:
    paths = []
    for path in ROOT.rglob("*.json"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        paths.append(path)
    return sorted(paths)


def main() -> int:
    errors: list[str] = []
    files = iter_json()
    for path in files:
        try:
            json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=no_duplicates_object_pairs_hook,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} JSON issue(s)")
        return 1
    print(f"OK: {len(files)} JSON file(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
