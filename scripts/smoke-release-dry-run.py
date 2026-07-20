#!/usr/bin/env python3
"""Smoke-test release dry-run without running the recursive full gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "release-dry-run.py"), "--skip-check", "--version", "0.0.1", "--profile", "minimal", "--provider", "generic"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stdout, end="")
        return proc.returncode
    if "OK: release dry-run passed" not in proc.stdout:
        print(f"FAIL: unexpected release dry-run output:\n{proc.stdout}")
        return 1
    print("OK: release dry-run smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
