#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate AgtMLS pre-1.0 version sequencing policy."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import skill_roots  # noqa: E402  (scripts path first)

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
METADATA_FILES = [
    ROOT / ".claude-plugin" / "plugin.json",
]
#: Files that must NOT carry a version. A version here is stamped with the
#: registry's on every release, and these are inside each skill's content
#: address -- so restoring one would make every release move every digest
#: again, and `verify` could not tell a bump from tampering.
VERSION_FREE = sorted(p / "metadata.json" for p in skill_roots.skill_dirs(ROOT) if (p / "metadata.json").exists()) + [
    ROOT / "templates" / "skill" / "metadata.json",
]


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def read_object(path: Path, errors: list[str]) -> dict:
    """The JSON object in `path`; {} (and a refusal in `errors`) for any other value."""
    data = read_json(path)
    if isinstance(data, dict):
        return data
    errors.append(f"{path.relative_to(ROOT)} must be a JSON object")
    return {}


def _has_version(data: object) -> bool:
    """Whether a version-free file mentions a version; a number or null cannot."""
    return isinstance(data, (dict, list, str)) and "version" in data


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


def tag_errors(current: str, patch: int, tags: list[tuple[int, int, int]]) -> list[str]:
    """The current version against the release tags that exist."""
    errors: list[str] = []
    if any((tag_major, tag_minor) != (0, 0) for tag_major, tag_minor, _ in tags) and (0, 0, 999) not in tags:
        errors.append("minor/major release tags are forbidden until v0.0.999 exists")
    patch_tags = [tag_patch for tag_major, tag_minor, tag_patch in tags if (tag_major, tag_minor) == (0, 0)]
    if not patch_tags:
        return errors
    latest_patch = max(patch_tags)
    if patch < latest_patch:
        errors.append(f"current version {current} is behind latest tag v0.0.{latest_patch}")
    if patch > latest_patch + 1:
        errors.append(
            f"current version {current} skips patch releases; next allowed after v0.0.{latest_patch} is 0.0.{latest_patch + 1}"
        )
    return errors


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
    return errors + tag_errors(current, patch, tags)


def metadata_errors(current: str) -> list[str]:
    errors = []
    for path in METADATA_FILES:
        version = str(_mapping(read_json(path)).get("version", ""))
        if version != current:
            errors.append(f"{path.relative_to(ROOT)} version {version} must match {current}")
    return errors


def version_free_errors() -> list[str]:
    errors = [
        f"{path.relative_to(ROOT)} must not carry a version: it would put "
        "the release back inside the skill's content address"
        for path in VERSION_FREE if path.exists() and _has_version(read_json(path))
    ]
    return errors + [
        f"{skill_md.relative_to(ROOT)} must not carry agtmls-version"
        for skill_md in skill_roots.skill_files(ROOT) if "agtmls-version" in skill_md.read_text(encoding="utf-8")
    ]


def provenance_errors(current: str) -> list[str]:
    # provenance.json is an in-toto Statement. A subject carries `name` and
    # `digest` and has no `version` field, so the registry version is read
    # from the predicate's externalParameters, and the subject name must still
    # embed it -- both are checked, because either drifting is a real defect.
    errors: list[str] = []
    provenance = read_object(ROOT / "provenance.json", errors)
    subject = provenance.get("subject", [{}])
    if not isinstance(subject, list) or not subject:
        errors.append("provenance.json must carry an in-toto subject list")
    elif _mapping(subject[0]).get("name") != f"agtmls-{current}":
        errors.append(
            f"provenance.json subject name must be 'agtmls-{current}', "
            f"got {_mapping(subject[0]).get('name')!r}"
        )
    predicate = _mapping(provenance.get("predicate", {}))
    parameters = _mapping(_mapping(predicate.get("buildDefinition", {})).get("externalParameters", {}))
    declared = parameters.get("registryVersion")
    if declared != current:
        errors.append("provenance.json registryVersion must match plugin version")
    return errors


def document_errors(current: str) -> list[str]:
    """The changelog entry and the policy text the release depends on."""
    errors = []
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## {current} - " not in changelog:
        errors.append(f"CHANGELOG.md must contain a dated ## {current} release entry")
    policy = (ROOT / "VERSIONING.md").read_text(encoding="utf-8") if (ROOT / "VERSIONING.md").exists() else ""
    for required in ["Versions increment by exactly `0.0.1`", "`v0.1.0` is forbidden until `v0.0.999`"]:
        if required not in policy:
            errors.append(f"VERSIONING.md must document: {required}")
    return errors


def main() -> int:
    errors: list[str] = []
    plugin = read_object(ROOT / ".claude-plugin" / "plugin.json", errors)
    current = str(plugin.get("version", ""))
    errors.extend(sequencing_errors(current, []))
    errors += metadata_errors(current) + version_free_errors()

    index = read_object(ROOT / "index.json", errors)
    if index.get("registry_version") != current:
        errors.append("index.json registry_version must match plugin version")
    errors += provenance_errors(current) + document_errors(current)

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
