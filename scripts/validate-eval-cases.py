#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate routing and behavioral eval case schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import skill_roots  # noqa: E402  (scripts path first)

SKILLS_DIR = ROOT / "skills"
ROUTING_DIR = ROOT / "evals" / "cases"
BEHAVIORAL_DIR = ROOT / "evals" / "behavioral" / "cases"


def skill_names() -> set[str]:
    return {p.name for p in skill_roots.skill_dirs(ROOT)}


def string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def load_case(cf: Path) -> tuple[dict, list[str]]:
    """(the case, []), or ({}, why it is not a JSON object)."""
    try:
        case = json.loads(cf.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"{cf.relative_to(ROOT)}: invalid JSON: {exc}"]
    if not isinstance(case, dict):
        return {}, [f"{cf.relative_to(ROOT)}: case must be a JSON object"]
    return case, []


def identity_problems(cf: Path, case: dict, kind: str, names: set[str], seen: set[str]) -> list[str]:
    """The case names a known skill, matches its filename, and is the only one; records it in `seen`."""
    errors = []
    # A list or object is no skill name, and cannot be looked up in a set.
    skill = case.get("skill")
    if not isinstance(skill, str) or skill not in names:
        errors.append(f"{cf.relative_to(ROOT)}: unknown skill {skill!r}")
    if cf.stem != skill:
        errors.append(f"{cf.relative_to(ROOT)}: filename must match skill")
    if isinstance(skill, str) and skill in seen:
        errors.append(f"{cf.relative_to(ROOT)}: duplicate {kind} case for {skill}")
    seen.add(str(skill))
    return errors


def validate_routing(names: set[str]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for cf in sorted(ROUTING_DIR.glob("*.json")):
        case, problems = load_case(cf)
        errors += problems
        if problems:
            continue
        errors += identity_problems(cf, case, "routing", names, seen)
        if not string_list(case.get("positive")):
            errors.append(f"{cf.relative_to(ROOT)}: positive must be a non-empty string list")
        if not string_list(case.get("negative")):
            errors.append(f"{cf.relative_to(ROOT)}: negative must be a non-empty string list")
    missing = sorted(names - seen)
    if missing:
        errors.append(f"missing routing cases: {', '.join(missing)}")
    return errors


ALLOWED_REQUIRES = {"files_exist", "skill_contains", "reference_contains"}
ALLOWED_FORBIDS = {"skill_contains", "reference_contains"}


def nonempty_strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def expectation_shapes(cf: Path, case: dict) -> tuple[dict, dict, list[str]]:
    """(requires, forbids, shape problems): each section that is not an
    object is reported here and read as empty, before any key is judged."""
    errors = []
    requires = case.get("requires", {})
    forbids = case.get("forbids", {})
    if not isinstance(requires, dict) or not requires:
        errors.append(f"{cf.relative_to(ROOT)}: requires must be a non-empty object")
        requires = {}
    if not isinstance(forbids, dict):
        errors.append(f"{cf.relative_to(ROOT)}: forbids must be an object")
        forbids = {}
    return requires, forbids, errors


def key_problems(cf: Path, section: str, entries: dict, allowed: set[str], valid, shape: str) -> list[str]:
    errors = []
    for key, value in entries.items():
        if key not in allowed:
            errors.append(f"{cf.relative_to(ROOT)}: unsupported {section} key {key!r}")
        if not valid(value):
            errors.append(f"{cf.relative_to(ROOT)}: {section}.{key} must be {shape}")
    return errors


def validate_behavioral(names: set[str]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for cf in sorted(BEHAVIORAL_DIR.glob("*.json")):
        case, problems = load_case(cf)
        errors += problems
        if problems:
            continue
        errors += identity_problems(cf, case, "behavioral", names, seen)
        requires, forbids, shape_errors = expectation_shapes(cf, case)
        errors += shape_errors
        errors += key_problems(cf, "requires", requires, ALLOWED_REQUIRES, string_list, "a non-empty string list")
        errors += key_problems(cf, "forbids", forbids, ALLOWED_FORBIDS, nonempty_strings, "a string list")
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
