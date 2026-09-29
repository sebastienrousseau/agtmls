#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Run deterministic behavioral smoke checks for skill contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import skill_roots  # noqa: E402  (scripts path first)

SKILLS_DIR = ROOT / "skills"
CASES_DIR = ROOT / "evals" / "behavioral" / "cases"


def skill_dir(name: str) -> Path | None:
    matches = [p for p in skill_roots.skill_dirs(ROOT) if p.name == name]
    return matches[0] if matches else None


def contains_all(label: str, text: str, needles: list[str], case_name: str) -> list[str]:
    return [f"{case_name}: {label} missing {needle!r}" for needle in needles if needle not in text]


def contains_none(label: str, text: str, needles: list[str], case_name: str) -> list[str]:
    return [f"{case_name}: {label} contains forbidden {needle!r}" for needle in needles if needle in text]


# (section, key, text it reads, check), in the order the runner applies them.
RULES = (
    ("requires", "files_exist", None, None),
    ("requires", "skill_contains", "SKILL.md", contains_all),
    ("requires", "reference_contains", "reference.md", contains_all),
    ("forbids", "skill_contains", "SKILL.md", contains_none),
    ("forbids", "reference_contains", "reference.md", contains_none),
)


def needles(cf: Path, case: dict, section: str, key: str) -> tuple[list[str], list[str]]:
    """(the strings a rule lists, why they cannot be read), for one section key.
    A string would be checked one character at a time, so it is refused."""
    mapping = case.get(section, {})
    if not isinstance(mapping, dict):
        return [], []
    value = mapping.get(key, [])
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value, []
    return [], [f"{cf.name}: {section}.{key} must be a list of strings"]


def expectation_results(cf: Path, sdir: Path, case: dict) -> tuple[list[str], int]:
    """(problems, checks) for one skill's requires and forbids."""
    texts = {
        "SKILL.md": (sdir / "SKILL.md").read_text(encoding="utf-8"),
        "reference.md": "\n".join(p.read_text(encoding="utf-8") for p in sorted(sdir.glob("reference*.md"))),
    }
    errors = [f"{cf.name}: {section} must be an object" for section in ("requires", "forbids")
              if not isinstance(case.get(section, {}), dict)]
    checks = 0
    for section, key, label, check in RULES:
        values, problems = needles(cf, case, section, key)
        errors += problems
        checks += len(values)
        for value in values:
            if check is None:
                errors += [] if (sdir / value).exists() else [f"{cf.name}: required file missing: {value}"]
            else:
                errors.extend(check(label, texts[label], [value], cf.name))
    return errors, checks


def load_case(cf: Path) -> tuple[dict, list[str]]:
    """(the case, []), or ({}, why it cannot be read as an object)."""
    try:
        case = json.loads(cf.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"{cf.name}: invalid JSON: {exc}"]
    if not isinstance(case, dict):
        return {}, [f"{cf.name}: not a JSON object"]
    return case, []


def case_results(cf: Path) -> tuple[list[str], int]:
    """(problems, checks) for one case file."""
    case, problems = load_case(cf)
    if problems:
        return problems, 0
    name = case.get("skill")
    sdir = skill_dir(name) if isinstance(name, str) else None
    if sdir is None:
        return [f"{cf.name}: unknown skill {name!r}"], 0
    return expectation_results(cf, sdir, case)


def main() -> int:
    case_files = sorted(CASES_DIR.glob("*.json")) if CASES_DIR.exists() else []
    if not case_files:
        print("no behavioral cases under evals/behavioral/cases/ — nothing to check")
        return 0

    errors: list[str] = []
    checks = 0
    for cf in case_files:
        found, checked = case_results(cf)
        errors += found
        checks += checked

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} behavioral issue(s) across {len(case_files)} case file(s)")
        return 1

    print(f"OK: {checks} behavioral checks passed across {len(case_files)} case file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
