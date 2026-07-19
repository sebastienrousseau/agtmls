#!/usr/bin/env python3
"""Validate routing and behavioral eval case schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
ROUTING_DIR = ROOT / "evals" / "cases"
BEHAVIORAL_DIR = ROOT / "evals" / "behavioral" / "cases"


def skill_names() -> set[str]:
    return {p.parent.name for p in SKILLS_DIR.glob("**/SKILL.md")}


def string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def validate_routing(names: set[str]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for cf in sorted(ROUTING_DIR.glob("*.json")):
        try:
            case = json.loads(cf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{cf.relative_to(ROOT)}: invalid JSON: {exc}")
            continue
        skill = case.get("skill")
        if skill not in names:
            errors.append(f"{cf.relative_to(ROOT)}: unknown skill {skill!r}")
        if cf.stem != skill:
            errors.append(f"{cf.relative_to(ROOT)}: filename must match skill")
        if skill in seen:
            errors.append(f"{cf.relative_to(ROOT)}: duplicate routing case for {skill}")
        seen.add(str(skill))
        if not string_list(case.get("positive")):
            errors.append(f"{cf.relative_to(ROOT)}: positive must be a non-empty string list")
        if not string_list(case.get("negative")):
            errors.append(f"{cf.relative_to(ROOT)}: negative must be a non-empty string list")
    missing = sorted(names - seen)
    if missing:
        errors.append(f"missing routing cases: {', '.join(missing)}")
    return errors


def validate_behavioral(names: set[str]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    allowed_requires = {"files_exist", "skill_contains", "reference_contains"}
    allowed_forbids = {"skill_contains", "reference_contains"}
    for cf in sorted(BEHAVIORAL_DIR.glob("*.json")):
        try:
            case = json.loads(cf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{cf.relative_to(ROOT)}: invalid JSON: {exc}")
            continue
        skill = case.get("skill")
        if skill not in names:
            errors.append(f"{cf.relative_to(ROOT)}: unknown skill {skill!r}")
        if cf.stem != skill:
            errors.append(f"{cf.relative_to(ROOT)}: filename must match skill")
        if skill in seen:
            errors.append(f"{cf.relative_to(ROOT)}: duplicate behavioral case for {skill}")
        seen.add(str(skill))
        requires = case.get("requires", {})
        forbids = case.get("forbids", {})
        if not isinstance(requires, dict) or not requires:
            errors.append(f"{cf.relative_to(ROOT)}: requires must be a non-empty object")
            requires = {}
        if not isinstance(forbids, dict):
            errors.append(f"{cf.relative_to(ROOT)}: forbids must be an object")
            forbids = {}
        for key, value in requires.items():
            if key not in allowed_requires:
                errors.append(f"{cf.relative_to(ROOT)}: unsupported requires key {key!r}")
            if not string_list(value):
                errors.append(f"{cf.relative_to(ROOT)}: requires.{key} must be a non-empty string list")
        for key, value in forbids.items():
            if key not in allowed_forbids:
                errors.append(f"{cf.relative_to(ROOT)}: unsupported forbids key {key!r}")
            if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                errors.append(f"{cf.relative_to(ROOT)}: forbids.{key} must be a string list")
    missing = sorted(names - seen)
    if missing:
        errors.append(f"missing behavioral cases: {', '.join(missing)}")
    return errors


def main() -> int:
    names = skill_names()
    errors = validate_routing(names) + validate_behavioral(names)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} eval schema issue(s)")
        return 1
    print(f"OK: eval schemas valid for {len(names)} skill(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
