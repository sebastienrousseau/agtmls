#!/usr/bin/env python3
"""Run shell syntax checks on repository shell scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__"}


def iter_shell() -> list[Path]:
    paths: list[Path] = []
    for ext in ("*.sh",):
        for path in ROOT.rglob(ext):
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            paths.append(path)
    return sorted(paths)


def main() -> int:
    errors: list[str] = []
    files = iter_shell()
    for path in files:
        proc = subprocess.run(
            ["bash", "-n", str(path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if proc.returncode != 0:
            errors.append(f"{path.relative_to(ROOT)}:\n{proc.stdout.rstrip()}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} shell syntax issue(s)")
        return 1
    print(f"OK: {len(files)} shell script(s) syntax-valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
