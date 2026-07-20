#!/usr/bin/env python3
"""Smoke-test next-version policy helper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "next-version.py")], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if proc.returncode != 0:
        print(proc.stdout, end="")
        return proc.returncode
    version = proc.stdout.strip()
    if version != "0.0.2":
        print(f"FAIL: expected next version 0.0.2 after v0.0.1, got {version}")
        return 1
    tag_proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "next-version.py"), "--tag"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if tag_proc.returncode != 0 or tag_proc.stdout.strip() != "v0.0.2":
        print(f"FAIL: expected next tag v0.0.2, got {tag_proc.stdout.strip()}")
        return 1
    print("OK: next-version smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
