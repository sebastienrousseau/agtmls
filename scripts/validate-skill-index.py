#!/usr/bin/env python3
"""Validate generated index.json beyond freshness."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.json"


def main() -> int:
    if not INDEX.exists():
        print("FAIL: index.json missing")
        return 1
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    errors: list[str] = []
    skills = data.get("skills", [])
    commands = data.get("commands", [])
    if data.get("skill_count") != len(skills):
        errors.append("skill_count does not match skills length")
    if data.get("command_count") != len(commands):
        errors.append("command_count does not match commands length")
    names = [skill.get("name") for skill in skills]
    if len(names) != len(set(names)):
        errors.append("duplicate skill names in index")
    for skill in skills:
        name = skill.get("name", "<unknown>")
        if not skill.get("path"):
            errors.append(f"{name}: missing path")
        elif not (ROOT / skill["path"] / "SKILL.md").exists():
            errors.append(f"{name}: indexed SKILL.md path does not exist")
        if not skill.get("description"):
            errors.append(f"{name}: missing description")
        if not skill.get("tags"):
            errors.append(f"{name}: missing tags")
        if not skill.get("evals", {}).get("routing"):
            errors.append(f"{name}: missing routing eval")
        if not skill.get("evals", {}).get("behavioral"):
            errors.append(f"{name}: missing behavioral eval")
    coverage = data.get("coverage", {})
    for key in ["routing", "behavioral"]:
        item = coverage.get(key, {})
        if item.get("covered") != item.get("total") or item.get("total") != len(skills):
            errors.append(f"{key} coverage summary is not complete")
    bundles = data.get("bundles", {})
    if sum(bundles.values()) != len(skills):
        errors.append("bundle counts do not sum to skill_count")
    command_names = [command.get("name") for command in commands]
    if len(command_names) != len(set(command_names)):
        errors.append("duplicate command names in index")
    for command in commands:
        name = command.get("name", "<unknown>")
        if not command.get("description"):
            errors.append(f"command {name}: missing description")
        if not command.get("path") or not (ROOT / command["path"]).exists():
            errors.append(f"command {name}: indexed path does not exist")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} index issue(s)")
        return 1
    print(f"OK: index metadata valid for {len(skills)} skill(s), {len(commands)} command(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
