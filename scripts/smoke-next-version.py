#!/usr/bin/env python3
"""Smoke-test next-version policy helper."""

from __future__ import annotations

import json
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
    parts = version.split(".")
    if len(parts) != 3 or parts[:2] != ["0", "0"] or not parts[2].isdigit():
        print(f"FAIL: next version does not follow 0.0.x policy: {version}")
        return 1
    tag_proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "next-version.py"), "--tag"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if tag_proc.returncode != 0 or tag_proc.stdout.strip() != f"v{version}":
        print(f"FAIL: expected next tag v{version}, got {tag_proc.stdout.strip()}")
        return 1
    json_proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "next-version.py"), "--json"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if json_proc.returncode != 0:
        print(json_proc.stdout, end="")
        return json_proc.returncode
    payload = json.loads(json_proc.stdout)
    if payload.get("version") != version or payload.get("tag") != f"v{version}":
        print(f"FAIL: inconsistent JSON payload: {json_proc.stdout.strip()}")
        return 1
    print("OK: next-version smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
