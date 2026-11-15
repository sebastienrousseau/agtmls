#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate release-facing metadata consistency."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _lib.checksums import parse_sums  # noqa: E402
from _lib.release_notes import CHECKSUMS, notes_problems, section  # noqa: E402

SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
# The fenced block a Checksums section lists its sums in.
FENCE = re.compile(r"^```[a-z]*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def recorded_sums(text: str) -> str | None:
    """The Checksums section when it records a well-formed SHA256SUMS listing,
    else None. Before its tag a release's notes say `pending`; once it is
    published they record the real sums, which must not fail this check."""
    fence = FENCE.search(section(text, CHECKSUMS) or "")
    listing = fence.group(1) if fence else ""
    sums, problems = parse_sums(listing)
    return listing if sums and not problems else None


def main() -> int:
    errors: list[str] = []
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    release = (ROOT / "RELEASE.md").read_text(encoding="utf-8")

    version = str(plugin.get("version", ""))
    if not SEMVER.match(version):
        errors.append("plugin version must be semver X.Y.Z")
    else:
        notes_file = ROOT / "docs" / "release-notes" / f"v{version}.md"
        if not notes_file.is_file():
            errors.append(f"docs/release-notes/v{version}.md must exist before releasing")
        else:
            text = notes_file.read_text(encoding="utf-8")
            errors.extend(notes_problems(notes_file.name, text, sums=recorded_sums(text), pending=True))

    if index.get("registry_version") != plugin.get("version"):
        errors.append("index registry_version must match plugin version")
    if index.get("name") != plugin.get("name"):
        errors.append("index name must match plugin name")
    if "## Unreleased" not in changelog:
        errors.append("CHANGELOG.md must contain ## Unreleased")
    if "python3 scripts/agtmls.py check" not in release:
        errors.append("RELEASE.md must require python3 scripts/agtmls.py check")
    if "python3 scripts/agtmls.py index --write" not in release:
        errors.append("RELEASE.md must require index regeneration")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} release metadata issue(s)")
        return 1
    print(f"OK: release metadata valid for {plugin['name']} {plugin['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
