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


MIN_POSITIVE = 3
MIN_NEGATIVE = 2


def owner_problems(label: str, case: dict, names: set[str]) -> list[str]:
    """Each negative's owner is a known skill, and not the case's own."""
    errors = []
    for index, entry in enumerate(case.get("negative") or []):
        owner = entry.get("owner") if isinstance(entry, dict) else None
        if isinstance(owner, str) and owner not in names:
            errors.append(f"{label}: negative[{index}] owner {owner!r} is not a skill")
        elif owner is not None and owner == case.get("skill"):
            errors.append(f"{label}: negative[{index}] owner is the case's own skill")
    return errors


def prompt_problems(cf: Path, case: dict, names: set[str]) -> list[str]:
    """At least three positive prompts, and at least two negatives that name
    the skill which should win them."""
    label = cf.relative_to(ROOT)
    errors = []
    positive = case.get("positive")
    if not string_list(positive) or len(positive) < MIN_POSITIVE:
        errors.append(f"{label}: positive needs at least {MIN_POSITIVE} prompts")
    negative = case.get("negative")
    pairs = isinstance(negative, list) and all(
        isinstance(n, dict) and string_list([n.get("prompt")]) and isinstance(n.get("owner"), str) for n in negative
    )
    if not pairs or len(negative) < MIN_NEGATIVE:
        errors.append(f"{label}: negative needs at least {MIN_NEGATIVE} {{prompt, owner}} entries")
    return errors + owner_problems(str(label), case, names)


def validate_routing(names: set[str]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for cf in sorted(ROUTING_DIR.glob("*.json")):
        case, problems = load_case(cf)
        errors += problems
        if problems:
            continue
        errors += identity_problems(cf, case, "routing", names, seen)
        errors += prompt_problems(cf, case, names)
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
