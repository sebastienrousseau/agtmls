#!/usr/bin/env python3
"""Smoke-test bump-version validation without mutating files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    next_proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "next-version.py")], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if next_proc.returncode != 0:
        print(next_proc.stdout, end="")
        return next_proc.returncode
    version = next_proc.stdout.strip()
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "bump-version.py"), "--check", "--version", version], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if proc.returncode != 0:
        print(proc.stdout, end="")
        return proc.returncode
    major, minor, patch = version.split(".")
    skipped = f"{major}.{minor}.{int(patch) + 1}"
    bad = subprocess.run([sys.executable, str(ROOT / "scripts" / "bump-version.py"), "--check", "--version", skipped], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if bad.returncode == 0:
        print("FAIL: bump-version --check accepted a skipped patch version")
        return 1
    print("OK: bump-version check smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
