#!/usr/bin/env python3
"""Compute the next allowed AgtMLS release version."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = re.compile(r"^v0\.0\.(\d+)$")
MAX_PATCH = 999


def release_patches() -> list[int]:
    proc = subprocess.run(
        ["git", "tag", "--list", "v0.0.*"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    patches: list[int] = []
    for line in proc.stdout.splitlines():
        match = TAG.match(line.strip())
        if match:
            patches.append(int(match.group(1)))
    return sorted(set(patches))


def next_version() -> str:
    patches = release_patches()
    if not patches:
        return "0.0.1"
    latest = max(patches)
    if latest >= MAX_PATCH:
        raise SystemExit("v0.0.999 already exists; 0.1.0 requires an explicit policy change")
    return f"0.0.{latest + 1}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", action="store_true", help="print with v prefix")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    version = next_version()
    payload = {"version": version, "tag": f"v{version}", "policy": "0.0.x increments by exactly 0.0.1"}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.tag:
        print(payload["tag"])
    else:
        print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
