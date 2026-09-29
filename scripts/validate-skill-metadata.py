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
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import skill_roots  # noqa: E402  (scripts path first)

SKILLS_DIR = ROOT / "skills"
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Every native agent AgtMLS installs into (providers.json): a skill may say
# it supports any of them. A hand-kept copy here stopped at claude, codex
# and aider after Antigravity became an install target.
AGENTS = set(json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))["native_agents"])
MATURITY = {"draft", "hardened", "project", "deprecated"}
NETWORK_ACCESS = {"none", "optional", "required"}
RISK_LEVELS = {"low", "medium", "high"}
SAFETY_BOOLEANS = ["writes_files", "executes_commands", "handles_secrets", "requires_human_review"]


def one_of(value: object, allowed: set[str]) -> bool:
    """Whether `value` is one of the allowed strings; a list or object is
    not, rather than raising when looked up in the set."""
    return isinstance(value, str) and value in allowed


def identity_problems(data: dict) -> list[str]:
    errors = []
    if "version" in data:
        errors.append(
            "must not carry a version; a skill is "
            "identified by its digest, and index.json records the release "
            "that last moved it"
        )
    if not data.get("owner"):
        errors.append("missing owner")
    # Bundle membership is a field, not a parent directory: the skill
    # tree is flat so every runtime's non-recursive scan finds all of it.
    if "bundle" not in data:
        errors.append("missing bundle (use null for general skills)")
    elif data["bundle"] is not None and not (
        isinstance(data["bundle"], str) and KEBAB.match(data["bundle"])
    ):
        errors.append("bundle must be null or kebab-case")
    return errors


def catalog_problems(data: dict) -> list[str]:
    errors = []
    if not one_of(data.get("maturity"), MATURITY):
        errors.append(f"maturity must be one of {sorted(MATURITY)}")
    agents = data.get("supported_agents", [])
    if not isinstance(agents, list) or not all(one_of(agent, AGENTS) for agent in agents):
        errors.append(f"supported_agents must be subset of {sorted(AGENTS)}")
    tools = data.get("required_tools", [])
    if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
        errors.append("required_tools must be a string list")
    return errors


def policy_problems(policy: object) -> list[str]:
    if not isinstance(policy, dict):
        return ["safety_policy must be an object"]
    errors = []
    if not one_of(policy.get("network_access"), NETWORK_ACCESS):
        errors.append(f"safety_policy.network_access must be one of {sorted(NETWORK_ACCESS)}")
    if not one_of(policy.get("risk_level"), RISK_LEVELS):
        errors.append(f"safety_policy.risk_level must be one of {sorted(RISK_LEVELS)}")
    errors += [f"safety_policy.{key} must be boolean" for key in SAFETY_BOOLEANS if not isinstance(policy.get(key), bool)]
    if policy.get("risk_level") == "high" and not policy.get("requires_human_review"):
        errors.append("high-risk skills must require human review")
    return errors


def hardened_problems(name: str, data: dict) -> list[str]:
    """A skill with an uplift case is hardened only once a run shows it helps
    (evals/uplift/README.md), recorded as an efficacy attestation that meets
    the bar. The release signs it. Skills without a case predate the rule."""
    if data.get("maturity") != "hardened" or not (ROOT / "evals/uplift/cases" / f"{name}.json").is_file():
        return []
    attestation = ROOT / "attestations" / name / "efficacy.intoto.json"
    try:
        meets = json.loads(attestation.read_text(encoding="utf-8"))["predicate"]["meets_bar"]
    except (OSError, ValueError, KeyError, TypeError):
        return [("hardened needs an efficacy attestation of its current bytes (run-uplift-evals.py, "
                 "then generate-skill-manifests.py --write)")]
    return [] if meets is True else ["hardened, but its efficacy attestation does not meet the bar"]


def file_problems(mf: Path) -> list[str]:
    """Every problem with one metadata.json, prefixed with its path."""
    where = mf.relative_to(ROOT)
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{where}: invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{where}: metadata must be an object"]
    found = identity_problems(data) + catalog_problems(data) + policy_problems(data.get("safety_policy"))
    found += hardened_problems(mf.parent.name, data)
    return [f"{where}: {problem}" for problem in found]


def main() -> int:
    errors: list[str] = []
    metadata_files = sorted(p / "metadata.json" for p in skill_roots.skill_dirs(ROOT) if (p / "metadata.json").exists())
    for mf in metadata_files:
        errors += file_problems(mf)

    # Every skill owns its metadata.json: the tree is flat, so there is no
    # bundle directory to inherit one from. Its contents were judged above;
    # parsing it again here crashed on the malformed file just reported.
    for skill_md in skill_roots.skill_files(ROOT):
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
