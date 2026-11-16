#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Every structured licence label agrees with pyproject.toml.

The repository is offered under one expression, `Apache-2.0 OR MIT`. A
manifest or index entry that says `MIT` alone tells a reader the Apache
grant does not apply to it, so this fails on a single drift. It reads:

- every JSON file: any `license`, `licenseDeclared` or `licenseConcluded`
  string, and CycloneDX `licenses[].expression`;
- `CITATION.cff`'s `license:` line.

SPDX headers and skill frontmatter are checked by
validate-licence-headers.py against the same expression. Two things are
deliberately not labels: `docs/evidence/` holds recorded agent runs, which
quote what a fixture said at the time, and an SPDX document's own
`dataLicense` (CC0-1.0) is required by the SPDX spec for its metadata.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import licence  # noqa: E402  (scripts path first)

SKIP_DIRS = {".git", "dist", "__pycache__", ".ruff_cache", ".agtmls", "node_modules", ".venv"}
RECORDS = ("docs", "evidence")
LABEL_KEYS = {"license", "licenseDeclared", "licenseConcluded"}
CITATION_LICENSE = re.compile(r"^license:\s*(.+?)\s*$", re.MULTILINE)


def labels(value: object, where: str = ""):
    """Yield (path, label) for every licence label inside a JSON value."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from member_labels(key, child, f"{where}.{key}" if where else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from labels(child, f"{where}[{index}]")


def member_labels(key: str, child: object, here: str):
    """One object member: a label itself, a CycloneDX list, or more to walk."""
    if key in LABEL_KEYS and isinstance(child, str):
        yield here, child
    elif key == "licenses" and isinstance(child, list):
        yield from expressions(child, here)
    else:
        yield from labels(child, here)


def expressions(entries: list, where: str):
    """CycloneDX writes the licence as `licenses: [{"expression": ...}]`."""
    for index, entry in enumerate(entries):
        if isinstance(entry, dict) and isinstance(entry.get("expression"), str):
            yield f"{where}[{index}].expression", entry["expression"]


def json_files() -> list[Path]:
    found = []
    for path in sorted(ROOT.rglob("*.json")):
        parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in parts) or parts[:2] == RECORDS:
            continue
        found.append(path)
    return found


def json_problems(path: Path, wanted: str) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []  # validate-json.py owns syntax; a label it cannot read is its finding
    return [
        f"{rel}: {where} is {label!r}, not {wanted!r}"
        for where, label in labels(data)
        if label != wanted
    ]


def citation_problems(wanted: str) -> list[str]:
    path = ROOT / "CITATION.cff"
    if not path.is_file():
        return []
    match = CITATION_LICENSE.search(path.read_text(encoding="utf-8"))
    if match is None:
        return ["CITATION.cff: no `license:` line"]
    found = match.group(1).strip("'\"")
    return [] if found == wanted else [f"CITATION.cff: license is {found!r}, not {wanted!r}"]


def main() -> int:
    wanted = licence.expression(ROOT)
    if wanted is None:
        print('FAIL: pyproject.toml: no `license = "..."` expression')
        return 1
    errors = citation_problems(wanted)
    files = json_files()
    for path in files:
        errors += json_problems(path, wanted)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} licence label(s) disagree with pyproject.toml")
        return 1
    print(f"OK: every licence label in {len(files)} JSON file(s) and CITATION.cff is {wanted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
