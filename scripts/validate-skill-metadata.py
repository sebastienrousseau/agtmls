#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate optional skill metadata.json files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
AGENTS = {"claude", "codex", "aider"}
MATURITY = {"draft", "hardened", "project", "deprecated"}
NETWORK_ACCESS = {"none", "optional", "required"}
RISK_LEVELS = {"low", "medium", "high"}
SAFETY_BOOLEANS = ["writes_files", "executes_commands", "handles_secrets", "requires_human_review"]


def main() -> int:
    errors: list[str] = []
    metadata_files = sorted(SKILLS_DIR.glob("*/metadata.json"))
    for mf in metadata_files:
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{mf.relative_to(ROOT)}: invalid JSON: {exc}")
            continue
        if "version" in data:
            errors.append(
                f"{mf.relative_to(ROOT)}: must not carry a version; a skill is "
                "identified by its digest, and index.json records the release "
                "that last moved it"
            )
        if not data.get("owner"):
            errors.append(f"{mf.relative_to(ROOT)}: missing owner")
        # Bundle membership is a field, not a parent directory: the skill
        # tree is flat so every runtime's non-recursive scan finds all of it.
        if "bundle" not in data:
            errors.append(f"{mf.relative_to(ROOT)}: missing bundle (use null for general skills)")
        elif data["bundle"] is not None and not (
            isinstance(data["bundle"], str) and KEBAB.match(data["bundle"])
        ):
            errors.append(f"{mf.relative_to(ROOT)}: bundle must be null or kebab-case")
        if data.get("maturity") not in MATURITY:
            errors.append(f"{mf.relative_to(ROOT)}: maturity must be one of {sorted(MATURITY)}")
        agents = data.get("supported_agents", [])
        if not isinstance(agents, list) or not set(agents).issubset(AGENTS):
            errors.append(f"{mf.relative_to(ROOT)}: supported_agents must be subset of {sorted(AGENTS)}")
        tools = data.get("required_tools", [])
        if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
            errors.append(f"{mf.relative_to(ROOT)}: required_tools must be a string list")
        policy = data.get("safety_policy")
        if not isinstance(policy, dict):
            errors.append(f"{mf.relative_to(ROOT)}: safety_policy must be an object")
        else:
            if policy.get("network_access") not in NETWORK_ACCESS:
                errors.append(f"{mf.relative_to(ROOT)}: safety_policy.network_access must be one of {sorted(NETWORK_ACCESS)}")
            if policy.get("risk_level") not in RISK_LEVELS:
                errors.append(f"{mf.relative_to(ROOT)}: safety_policy.risk_level must be one of {sorted(RISK_LEVELS)}")
            for key in SAFETY_BOOLEANS:
                if not isinstance(policy.get(key), bool):
                    errors.append(f"{mf.relative_to(ROOT)}: safety_policy.{key} must be boolean")
            if policy.get("risk_level") == "high" and not policy.get("requires_human_review"):
                errors.append(f"{mf.relative_to(ROOT)}: high-risk skills must require human review")

    # Every skill owns its metadata.json: the tree is flat, so there is no
    # bundle directory to inherit one from. Its contents were judged above;
    # parsing it again here crashed on the malformed file just reported.
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        if not (skill_md.parent / "metadata.json").is_file():
            errors.append(f"{skill_md.parent.relative_to(ROOT)}: no metadata.json")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} metadata issue(s)")
        return 1
    print(f"OK: {len(metadata_files)} metadata file(s) cover all skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
