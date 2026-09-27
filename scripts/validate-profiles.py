#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate install/export profile metadata."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles.json"
INDEX = ROOT / "index.json"
REQUIRED = {"minimal", "polyglot", "noyalib", "security", "research"}
# A project bundle serves one codebase; only the profile named after it may
# install it, so the general profiles stay general.
PROJECT_BUNDLES = {"noyalib"}


def string_list(profile: dict, name: str, key: str) -> tuple[list[str], list[str]]:
    """(the profile's `key` list, or [] when it is not a list of strings; problems)."""
    value = profile.get(key, [])
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value, []
    return [], [f"profile {name} {key} must be a string list"]


def reference_problems(name: str, ps: list[str], pb: list[str], skills: set[str], bundles: set[str]) -> list[str]:
    errors = [f"profile {name} references unknown skill: {skill}" for skill in ps if skill not in skills]
    for bundle in pb:
        if bundle not in bundles:
            errors.append(f"profile {name} references unknown bundle: {bundle}")
        elif bundle in PROJECT_BUNDLES and bundle != name:
            errors.append(f"profile {name} pulls in the {bundle} project bundle; only profile {bundle} may")
    if name in bundles and name not in pb:
        errors.append(f"profile {name} omits the {name} bundle it is named after")
    return errors


def profile_problems(name: str, profile: dict, skills: set[str], bundles: set[str]) -> tuple[list[str], list[str], list[str]]:
    """(problems, skills, bundles) of one profile that is an object."""
    errors = []
    if not isinstance(profile.get("description"), str) or not profile["description"].strip():
        errors.append(f"profile {name} missing description")
    ps, bad_skills = string_list(profile, name, "skills")
    pb, bad_bundles = string_list(profile, name, "bundles")
    errors += bad_skills + bad_bundles + reference_problems(name, ps, pb, skills, bundles)
    return errors, ps, pb


def index_sets(index: dict) -> tuple[set[str], dict[str, set[str]], set[str]]:
    """(skill names, skill names by bundle, bundle names) from index.json."""
    skills = {skill["name"] for skill in index.get("skills", [])}
    members: dict[str, set[str]] = {}
    for skill in index.get("skills", []):
        members.setdefault(skill.get("bundle") or "_general", set()).add(skill["name"])
    bundles = {name for name in index.get("bundles", {}) if name != "_general"}
    return skills, members, bundles


def root_problems(data: dict) -> tuple[list[str], dict]:
    """(problems with the document as a whole, its profiles)."""
    errors = []
    if data.get("schema_version") != 1:
        errors.append("profiles.json schema_version must be 1")
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        errors.append("profiles must be an object")
        profiles = {}
    errors += [f"missing required profile: {name}" for name in sorted(REQUIRED - set(profiles))]
    return errors, profiles


def main() -> int:
    data = json.loads(PROFILES.read_text(encoding="utf-8"))
    skills, members, bundles = index_sets(json.loads(INDEX.read_text(encoding="utf-8")))
    errors, profiles = root_problems(data)
    resolved: dict[frozenset[str], str] = {}
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            errors.append(f"profile {name} must be an object")
            continue
        found, ps, pb = profile_problems(name, profile, skills, bundles)
        errors += found
        installs = frozenset(ps).union(*(members.get(bundle, set()) for bundle in pb))
        if installs in resolved:
            errors.append(f"profile {name} installs exactly what profile {resolved[installs]} does")
        else:
            resolved[installs] = name
    return report(errors, len(profiles))


def report(errors: list[str], count: int) -> int:
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} profile metadata issue(s)")
        return 1
    print(f"OK: {count} install/export profile(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
