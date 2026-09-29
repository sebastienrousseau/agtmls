#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate lifecycle.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIFECYCLE = ROOT / "lifecycle.json"


STAGES = ["proposal", "draft", "hardened", "published"]
NON_NEGOTIABLES = [
    "no background transcript capture",
    "redact likely secrets before staging proposals",
    "do not auto-install generated skills",
    "do not edit index.json by hand",
]


def stage_problems(stages: list) -> list[str]:
    """The four stages, in order, each naming its artifacts and exit criteria."""
    errors = []
    if [stage.get("name") for stage in stages] != STAGES:
        errors.append(f"stages must be ordered as {STAGES}")
    for stage in stages:
        name = stage.get("name", "<unknown>")
        if not stage.get("required_artifacts"):
            errors.append(f"{name}: missing required_artifacts")
        if not stage.get("exit_criteria"):
            errors.append(f"{name}: missing exit_criteria")
    return errors


def main() -> int:
    if not LIFECYCLE.exists():
        print("FAIL: lifecycle.json missing")
        return 1
    data = json.loads(LIFECYCLE.read_text(encoding="utf-8"))
    errors: list[str] = [] if data.get("schema_version") == 1 else ["schema_version must be 1"]
    errors += stage_problems(data.get("stages", []))
    errors += [f"missing non-negotiable: {phrase}" for phrase in NON_NEGOTIABLES if phrase not in data.get("non_negotiables", [])]
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("OK: lifecycle metadata valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
