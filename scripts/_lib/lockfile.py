# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Install lockfile: what was installed, and what it hashed to.

Normative definition: agtmls-spec/spec/06-lockfile.md.

Without this there is no answer to "is what I have what you published?", and
the registry is a decorated `ln -s`. The lockfile is what turns a digest from
a number in a JSON file into a control.

It lives at `<target>/.agtmls/manifest.json`, which is excluded from the
digest by design -- an install must not change the identity of what it
installed.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from _lib.digest import skill_digest

SCHEMA_VERSION = 1
SPEC_VERSION = "0.1.0"
LOCKFILE_RELATIVE = Path(".agtmls") / "manifest.json"

# Exit code taxonomy. 0/1/2 conflates "worked", "something went wrong" and
# "you typed it wrong"; a tampered install deserves its own signal so a
# calling script can branch on it.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTEGRITY_FAILURE = 3


def lockfile_path(target: Path) -> Path:
    return target / LOCKFILE_RELATIVE


def executable_files(skill_dir: Path) -> list[str]:
    """Paths whose executable bit matters.

    Mode bits are deliberately excluded from the digest (spec 3.4) because the
    executable bit does not survive every transport. Recording them separately
    means a lost bit can be repaired without being mistaken for tampering.
    """
    found: list[str] = []
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file() and not path.is_symlink() and os.access(path, os.X_OK):
            found.append(path.relative_to(skill_dir).as_posix())
    return found


def build(target: Path, registry_root: Path, skills: list[str], mode: str,
          registry_version: str) -> dict[str, object]:
    """Describe an install that has just happened."""
    entries = []
    for name in sorted(skills):
        source = registry_root / "skills" / name
        if not source.is_dir():
            continue
        entries.append({
            "name": name,
            "integrity": skill_digest(source),
            "path": name,
            "executable_files": executable_files(source),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "spec_version": SPEC_VERSION,
        "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {
            "registry": "https://github.com/sebastienrousseau/agtmls",
            "registry_version": registry_version,
        },
        "mode": mode,
        "skills": entries,
    }


def write(target: Path, payload: dict[str, object]) -> Path:
    path = lockfile_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read(target: Path) -> dict[str, object] | None:
    path = lockfile_path(target)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def verify(target: Path, skills_dir: Path) -> list[tuple[str, str, str]]:
    """Compare an installed tree against its lockfile.

    Returns (name, status, detail) for everything that is not `ok`. An empty
    list means every recorded skill is byte-identical to what was installed.

    Deliberately reports rather than repairs: silently rewriting a skill whose
    digest moved would destroy a local edit, and would hide tampering behind
    the same behaviour.
    """
    lock = read(target)
    if lock is None:
        return [("", "no-lockfile", f"no {LOCKFILE_RELATIVE} in {target}")]

    problems: list[tuple[str, str, str]] = []
    recorded: set[str] = set()

    for entry in lock.get("skills", []):
        name = entry["name"]
        recorded.add(name)
        installed = skills_dir / entry.get("path", name)
        if not installed.exists():
            problems.append((name, "missing", "recorded in the lockfile but not installed"))
            continue
        actual = skill_digest(installed)
        if actual != entry["integrity"]:
            problems.append((
                name, "modified",
                f"expected {entry['integrity']}, found {actual}",
            ))

    # Present but unmanaged: reported, never removed. Deleting something we
    # have no record of installing is not ours to do.
    if skills_dir.is_dir():
        for path in sorted(skills_dir.iterdir()):
            if path.is_dir() and path.name not in recorded:
                problems.append((path.name, "unmanaged", "installed but not in the lockfile"))

    return problems
