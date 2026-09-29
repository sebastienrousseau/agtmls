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


def stage_problems(stages: object) -> list[str]:
    """The four stages, in order, each naming its artifacts and exit criteria."""
    if not isinstance(stages, list):
        return ["stages must be a list"]
    errors = [f"stage {i} must be an object" for i, stage in enumerate(stages) if not isinstance(stage, dict)]
    stages = [stage for stage in stages if isinstance(stage, dict)]
    if [stage.get("name") for stage in stages] != STAGES:
        errors.append(f"stages must be ordered as {STAGES}")
    return errors + [problem for stage in stages for problem in stage_fields(stage)]


def stage_fields(stage: dict) -> list[str]:
    name = stage.get("name", "<unknown>")
    return [f"{name}: missing {field}" for field in ("required_artifacts", "exit_criteria") if not stage.get(field)]


def load() -> dict | str:
    """lifecycle.json, or why it cannot be read as an object."""
    if not LIFECYCLE.exists():
        return "lifecycle.json missing"
    try:
        data = json.loads(LIFECYCLE.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return "lifecycle.json is not UTF-8 text"
    except json.JSONDecodeError as exc:
        return f"lifecycle.json is not valid JSON: {exc}"
    return data if isinstance(data, dict) else "lifecycle.json must be a JSON object"


def non_negotiable_problems(listed: object) -> list[str]:
    """Every non-negotiable is listed; a string is refused, since it would match by substring."""
    if not isinstance(listed, list):
        return ["non_negotiables must be a list"]
    return [f"missing non-negotiable: {phrase}" for phrase in NON_NEGOTIABLES if phrase not in listed]


def main() -> int:
    data = load()
    if isinstance(data, str):
        print(f"FAIL: {data}")
        return 1
    errors: list[str] = [] if data.get("schema_version") == 1 else ["schema_version must be 1"]
    errors += stage_problems(data.get("stages", []))
    errors += non_negotiable_problems(data.get("non_negotiables", []))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("OK: lifecycle metadata valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
