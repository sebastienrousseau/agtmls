#!/usr/bin/env python3
"""Run deterministic behavioral smoke checks for skill contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
CASES_DIR = ROOT / "evals" / "behavioral" / "cases"


def skill_dir(name: str) -> Path | None:
    matches = [p.parent for p in SKILLS_DIR.glob("**/SKILL.md") if p.parent.name == name]
    return matches[0] if matches else None


def contains_all(label: str, text: str, needles: list[str], case_name: str) -> list[str]:
    return [f"{case_name}: {label} missing {needle!r}" for needle in needles if needle not in text]


def contains_none(label: str, text: str, needles: list[str], case_name: str) -> list[str]:
    return [f"{case_name}: {label} contains forbidden {needle!r}" for needle in needles if needle in text]


def main() -> int:
    case_files = sorted(CASES_DIR.glob("*.json")) if CASES_DIR.exists() else []
    if not case_files:
        print("no behavioral cases under evals/behavioral/cases/ — nothing to check")
        return 0

    errors: list[str] = []
    checks = 0
    for cf in case_files:
        case = json.loads(cf.read_text(encoding="utf-8"))
        name = case["skill"]
        sdir = skill_dir(name)
        if sdir is None:
            errors.append(f"{cf.name}: unknown skill {name!r}")
            continue

        skill_text = (sdir / "SKILL.md").read_text(encoding="utf-8")
        ref_text = "\n".join(
            p.read_text(encoding="utf-8") for p in sorted(sdir.glob("reference*.md"))
        )
        requires = case.get("requires", {})
        forbids = case.get("forbids", {})

        for rel in requires.get("files_exist", []):
            checks += 1
            if not (sdir / rel).exists():
                errors.append(f"{cf.name}: required file missing: {rel}")
        for needle in requires.get("skill_contains", []):
            checks += 1
            errors.extend(contains_all("SKILL.md", skill_text, [needle], cf.name))
        for needle in requires.get("reference_contains", []):
            checks += 1
            errors.extend(contains_all("reference.md", ref_text, [needle], cf.name))
        for needle in forbids.get("skill_contains", []):
            checks += 1
            errors.extend(contains_none("SKILL.md", skill_text, [needle], cf.name))

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
