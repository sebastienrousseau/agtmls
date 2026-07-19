#!/usr/bin/env python3
"""Validate install/export profile metadata."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles.json"
INDEX = ROOT / "index.json"
REQUIRED = {"minimal", "polyglot", "noyalib", "security", "research"}


def main() -> int:
    errors: list[str] = []
    data = json.loads(PROFILES.read_text(encoding="utf-8"))
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    skills = {skill["name"] for skill in index.get("skills", [])}
    bundles = {name for name in index.get("bundles", {}) if name != "_general"}
    if data.get("schema_version") != 1:
        errors.append("profiles.json schema_version must be 1")
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        errors.append("profiles must be an object")
        profiles = {}
    for name in sorted(REQUIRED - set(profiles)):
        errors.append(f"missing required profile: {name}")
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            errors.append(f"profile {name} must be an object")
            continue
        if not isinstance(profile.get("description"), str) or not profile["description"].strip():
            errors.append(f"profile {name} missing description")
        ps = profile.get("skills", [])
        pb = profile.get("bundles", [])
        if not isinstance(ps, list) or not all(isinstance(item, str) for item in ps):
            errors.append(f"profile {name} skills must be a string list")
            ps = []
        if not isinstance(pb, list) or not all(isinstance(item, str) for item in pb):
            errors.append(f"profile {name} bundles must be a string list")
            pb = []
        for skill in ps:
            if skill not in skills:
                errors.append(f"profile {name} references unknown skill: {skill}")
        for bundle in pb:
            if bundle not in bundles:
                errors.append(f"profile {name} references unknown bundle: {bundle}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} profile metadata issue(s)")
        return 1
    print(f"OK: {len(profiles)} install/export profile(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
