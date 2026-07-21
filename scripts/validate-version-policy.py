#!/usr/bin/env python3
"""Validate AgtMLS pre-1.0 version sequencing policy."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
METADATA_FILES = [
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / "skills" / "cross-language-port" / "metadata.json",
    ROOT / "skills" / "engineering" / "metadata.json",
    ROOT / "skills" / "loops" / "metadata.json",
    ROOT / "skills" / "noyalib" / "metadata.json",
    ROOT / "skills" / "security" / "metadata.json",
    ROOT / "skills" / "using-agtmls" / "metadata.json",
    ROOT / "skills" / "web-reach" / "metadata.json",
]


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_version(value: str) -> tuple[int, int, int] | None:
    match = SEMVER.match(value)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def release_tags() -> list[tuple[int, int, int]]:
    proc = subprocess.run(
        ["git", "tag", "--list", "v*"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    tags: list[tuple[int, int, int]] = []
    for line in proc.stdout.splitlines():
        match = TAG.match(line.strip())
        if match:
            tags.append(tuple(int(part) for part in match.groups()))
    return sorted(tags)


def sequencing_errors(current: str, tags: list[tuple[int, int, int]]) -> list[str]:
    errors: list[str] = []
    parsed = parse_version(current)
    if parsed is None:
        return ["plugin version must be semver X.Y.Z"]
    major, minor, patch = parsed
    if major != 0 or minor != 0:
        errors.append("public releases must stay on the 0.0.x line")
    if patch < 1 or patch > 999:
        errors.append("0.0.x patch must be between 1 and 999")
    if tags:
        if any((tag_major, tag_minor) != (0, 0) for tag_major, tag_minor, _ in tags) and (0, 0, 999) not in tags:
            errors.append("minor/major release tags are forbidden until v0.0.999 exists")
        patch_tags = [tag_patch for tag_major, tag_minor, tag_patch in tags if (tag_major, tag_minor) == (0, 0)]
        if patch_tags:
            latest_patch = max(patch_tags)
            if patch < latest_patch:
                errors.append(f"current version {current} is behind latest tag v0.0.{latest_patch}")
            if patch > latest_patch + 1:
                errors.append(
                    f"current version {current} skips patch releases; next allowed after v0.0.{latest_patch} is 0.0.{latest_patch + 1}"
                )
    return errors


def main() -> int:
    errors: list[str] = []
    plugin = read_json(ROOT / ".claude-plugin" / "plugin.json")
    current = str(plugin.get("version", ""))
    parsed = parse_version(current)
    errors.extend(sequencing_errors(current, []))

    for path in METADATA_FILES:
        version = str(read_json(path).get("version", ""))
        if version != current:
            errors.append(f"{path.relative_to(ROOT)} version {version} must match {current}")

    index = read_json(ROOT / "index.json")
    if index.get("registry_version") != current:
        errors.append("index.json registry_version must match plugin version")
    agent_card = read_json(ROOT / "agent-card.json")
    if agent_card.get("version") != current:
        errors.append("agent-card.json version must match plugin version")
    provenance = read_json(ROOT / "provenance.json")
    subject = provenance.get("subject", [{}])
    if not isinstance(subject, list) or not subject or subject[0].get("version") != current:
        errors.append("provenance.json subject version must match plugin version")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## {current} - " not in changelog:
        errors.append(f"CHANGELOG.md must contain a dated ## {current} release entry")
    policy = (ROOT / "VERSIONING.md").read_text(encoding="utf-8") if (ROOT / "VERSIONING.md").exists() else ""
    for required in ["Versions increment by exactly `0.0.1`", "`v0.1.0` is forbidden until `v0.0.999`"]:
        if required not in policy:
            errors.append(f"VERSIONING.md must document: {required}")

    tags = release_tags()
    errors.extend(error for error in sequencing_errors(current, tags) if error not in errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} version policy issue(s)")
        return 1
    print(f"OK: version policy valid for {current}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
