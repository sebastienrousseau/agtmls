#!/usr/bin/env python3
"""Validate lifecycle.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIFECYCLE = ROOT / "lifecycle.json"


def main() -> int:
    if not LIFECYCLE.exists():
        print("FAIL: lifecycle.json missing")
        return 1
    data = json.loads(LIFECYCLE.read_text(encoding="utf-8"))
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    stages = data.get("stages", [])
    expected = ["proposal", "draft", "hardened", "published"]
    names = [stage.get("name") for stage in stages]
    if names != expected:
        errors.append(f"stages must be ordered as {expected}")
    for stage in stages:
        name = stage.get("name", "<unknown>")
        if not stage.get("required_artifacts"):
            errors.append(f"{name}: missing required_artifacts")
        if not stage.get("exit_criteria"):
            errors.append(f"{name}: missing exit_criteria")
    for phrase in [
        "no background transcript capture",
        "redact likely secrets before staging proposals",
        "do not auto-install generated skills",
        "do not edit index.json by hand",
    ]:
        if phrase not in data.get("non_negotiables", []):
            errors.append(f"missing non-negotiable: {phrase}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("OK: lifecycle metadata valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
