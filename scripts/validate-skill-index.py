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


def as_object(value: object) -> dict:
    """`value` when it is an object, else an empty one: a summary of the
    wrong shape is then reported as incomplete rather than raised."""
    return value if isinstance(value, dict) else {}


def entries(data: dict, key: str) -> tuple[list, list[dict], list[str]]:
    """(the `key` array or [], its object entries, shape problems)."""
    value = data.get(key, [])
    if not isinstance(value, list):
        return [], [], [f"{key} must be an array"]
    errors = [f"{key} entry {i} must be an object" for i, item in enumerate(value) if not isinstance(item, dict)]
    return value, [item for item in value if isinstance(item, dict)], errors


def name_problems(kind: str, items: list[dict]) -> list[str]:
    """A name must be a string; one that is not cannot be looked up."""
    return [f"{kind} name must be a string: {item['name']!r}"
            for item in items if "name" in item and not isinstance(item["name"], str)]


def skill_path_problem(name: str, skill: dict) -> list[str]:
    if not skill.get("path"):
        return [f"{name}: missing path"]
    if not isinstance(skill["path"], str):
        return [f"{name}: path must be a string"]
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
    evals = as_object(skill.get("evals"))
    if not evals.get("routing"):
        errors.append(f"{name}: missing routing eval")
    if not evals.get("behavioral"):
        errors.append(f"{name}: missing behavioral eval")
    return errors + skill_quality_problem(name, skill)


def command_problems(command: dict) -> list[str]:
    name = command.get("name", "<unknown>")
    errors = []
    if not command.get("description"):
        errors.append(f"command {name}: missing description")
    path = command.get("path")
    if not path or not isinstance(path, str) or not (ROOT / path).exists():
        errors.append(f"command {name}: indexed path does not exist")
    return errors


def summary_problems(data: dict, skills: list) -> list[str]:
    """The coverage, quality and bundle totals against the skills listed."""
    errors = []
    coverage = as_object(data.get("coverage"))
    for key in ["routing", "behavioral"]:
        item = as_object(coverage.get(key))
        if item.get("covered") != item.get("total") or item.get("total") != len(skills):
            errors.append(f"{key} coverage summary is not complete")
    quality = data.get("quality", {})
    if not isinstance(quality, dict) or not isinstance(quality.get("average_score"), int):
        errors.append("missing aggregate quality score")
    return errors + bundle_problems(data.get("bundles", {}), len(skills))


def bundle_problems(bundles: object, skill_count: int) -> list[str]:
    if not isinstance(bundles, dict) or not all(isinstance(count, int) for count in bundles.values()):
        return ["bundles must map bundle names to integer counts"]
    if sum(bundles.values()) != skill_count:
        return ["bundle counts do not sum to skill_count"]
    return []


def has_duplicates(items: list[dict]) -> bool:
    names = [item.get("name") for item in items if item.get("name") is None or isinstance(item["name"], str)]
    return len(names) != len(set(names))


def index_problems(data: dict) -> list[str]:
    all_skills, skills, errors = entries(data, "skills")
    all_commands, commands, command_errors = entries(data, "commands")
    errors += command_errors + name_problems("skill", skills) + name_problems("command", commands)
    return errors + count_problems(data, all_skills, all_commands) + entry_problems(data, skills, commands)


def count_problems(data: dict, skills: list, commands: list) -> list[str]:
    errors: list[str] = []
    if data.get("skill_count") != len(skills):
        errors.append("skill_count does not match skills length")
    if data.get("command_count") != len(commands):
        errors.append("command_count does not match commands length")
    return errors


def entry_problems(data: dict, skills: list[dict], commands: list[dict]) -> list[str]:
    errors: list[str] = []
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
    try:
        data = json.loads(INDEX.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: index.json invalid: {exc}")
        return 1
    if not isinstance(data, dict):
        print("FAIL: index.json must be an object")
        return 1
    errors = index_problems(data)
    skills, commands = entries(data, "skills")[1], entries(data, "commands")[1]

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
