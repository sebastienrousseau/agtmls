#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate generated index.json beyond freshness."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.json"


def skill_path_problem(name: str, skill: dict) -> list[str]:
    if not skill.get("path"):
        return [f"{name}: missing path"]
    if not (ROOT / skill["path"] / "SKILL.md").exists():
        return [f"{name}: indexed SKILL.md path does not exist"]
    return []


def skill_quality_problem(name: str, skill: dict) -> list[str]:
    quality = skill.get("quality", {})
    if not isinstance(quality, dict) or not isinstance(quality.get("score"), int):
        return [f"{name}: missing integer quality score"]
    if quality.get("score", 0) < 75:
        return [f"{name}: quality score below publication threshold"]
    return []


def skill_problems(skill: dict) -> list[str]:
    name = skill.get("name", "<unknown>")
    errors = skill_path_problem(name, skill)
    if not skill.get("description"):
        errors.append(f"{name}: missing description")
    if not skill.get("tags"):
        errors.append(f"{name}: missing tags")
    if not skill.get("evals", {}).get("routing"):
        errors.append(f"{name}: missing routing eval")
    if not skill.get("evals", {}).get("behavioral"):
        errors.append(f"{name}: missing behavioral eval")
    return errors + skill_quality_problem(name, skill)


def command_problems(command: dict) -> list[str]:
    name = command.get("name", "<unknown>")
    errors = []
    if not command.get("description"):
        errors.append(f"command {name}: missing description")
    if not command.get("path") or not (ROOT / command["path"]).exists():
        errors.append(f"command {name}: indexed path does not exist")
    return errors


def summary_problems(data: dict, skills: list) -> list[str]:
    """The coverage, quality and bundle totals against the skills listed."""
    errors = []
    coverage = data.get("coverage", {})
    for key in ["routing", "behavioral"]:
        item = coverage.get(key, {})
        if item.get("covered") != item.get("total") or item.get("total") != len(skills):
            errors.append(f"{key} coverage summary is not complete")
    quality = data.get("quality", {})
    if not isinstance(quality, dict) or not isinstance(quality.get("average_score"), int):
        errors.append("missing aggregate quality score")
    bundles = data.get("bundles", {})
    if sum(bundles.values()) != len(skills):
        errors.append("bundle counts do not sum to skill_count")
    return errors


def has_duplicates(items: list) -> bool:
    names = [item.get("name") for item in items]
    return len(names) != len(set(names))


def index_problems(data: dict, skills: list, commands: list) -> list[str]:
    errors: list[str] = []
    if data.get("skill_count") != len(skills):
        errors.append("skill_count does not match skills length")
    if data.get("command_count") != len(commands):
        errors.append("command_count does not match commands length")
    if has_duplicates(skills):
        errors.append("duplicate skill names in index")
    for skill in skills:
        errors += skill_problems(skill)
    errors += summary_problems(data, skills)
    if has_duplicates(commands):
        errors.append("duplicate command names in index")
    for command in commands:
        errors += command_problems(command)
    return errors


def main() -> int:
    if not INDEX.exists():
        print("FAIL: index.json missing")
        return 1
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    skills = data.get("skills", [])
    commands = data.get("commands", [])
    errors = index_problems(data, skills, commands)

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
