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

from _lib import skill_roots
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
# agtmls-spec 9.5 and 11.4.
EXIT_UNSIGNED = 4
EXIT_BAD_SIGNATURE = 5
EXIT_REVOKED = 6


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


def _entry(registry_root: Path, name: str, agents: list[str]) -> dict[str, object] | None:
    source = skill_roots.find(registry_root, name)
    if source is None:
        return None
    return {
        "name": name,
        "integrity": skill_digest(source),
        "path": name,
        "executable_files": executable_files(source),
        "agents": agents,
    }


def build(target: Path, registry_root: Path, skills: list[str], mode: str,
          registry_version: str, agent: str | None = None) -> dict[str, object]:
    """Describe an install that has just happened.

    With `agent`, each entry records it in `agents` (agtmls-spec 6.2); `record`
    merges that into a lockfile other agents already share.
    """
    entries = [
        entry for name in sorted(skills)
        if (entry := _entry(registry_root, name, [agent] if agent else [])) is not None
    ]
    if agent is None:
        for entry in entries:
            del entry["agents"]
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


def resolve_agents(lock: dict[str, object], skills_dirs: dict[str, Path]) -> dict[str, object]:
    """Give every entry an `agents` list.

    An entry written before `agents` existed counts for every agent; once the
    lockfile is rewritten it names the agents whose skills directory holds
    that skill now, so the record stops claiming skills an agent never had.
    `skills_dirs` maps each native agent to its skills directory in the target.
    """
    for entry in lock.get("skills", []):
        if "agents" not in entry:
            entry["agents"] = sorted(
                agent for agent, directory in skills_dirs.items()
                if (directory / entry.get("path", entry["name"])).exists()
            )
    return lock


def _join(entries: list[dict[str, object]], fresh: dict[str, object], agent: str) -> None:
    """Add `agent` to the entry for `fresh`'s name at its digest, or add
    `fresh` as a new entry: two agents holding different versions of a
    skill keep one entry each."""
    same = next((e for e in entries if e["name"] == fresh["name"] and e["integrity"] == fresh["integrity"]), None)
    if same is None:
        entries.append(fresh)
        return
    same["agents"] = sorted({*same["agents"], agent})
    same["executable_files"] = fresh["executable_files"]


def record(target: Path, registry_root: Path, skills: list[str], mode: str,
           registry_version: str, agent: str, skills_dirs: dict[str, Path]) -> dict[str, object]:
    """The lockfile after installing `skills` for `agent`.

    One lockfile serves every agent in a target. Only `agent`'s record is
    replaced: it leaves every entry, joins the entries for what it installed
    now, and entries no agent holds are dropped.
    """
    payload = build(target, registry_root, skills, mode, registry_version, agent)
    previous = read(target)
    entries = resolve_agents(previous, skills_dirs).get("skills", []) if previous else []
    for entry in entries:
        entry["agents"] = [a for a in entry["agents"] if a != agent]
    for fresh in payload["skills"]:
        _join(entries, fresh, agent)
    payload["skills"] = sorted((e for e in entries if e["agents"]), key=lambda e: (e["name"], e["integrity"]))
    return payload


def forget(lock: dict[str, object], agent: str, skills_dirs: dict[str, Path],
           kept: frozenset[str] = frozenset()) -> dict[str, object]:
    """The lockfile after uninstalling `agent`: every other agent's record
    kept, and `agent`'s own for the skills in `kept`, which uninstall left in
    place (a local edit) so verify can still report them."""
    resolve_agents(lock, skills_dirs)
    for entry in lock.get("skills", []):
        if entry["name"] not in kept:
            entry["agents"] = [a for a in entry["agents"] if a != agent]
    lock["skills"] = [e for e in lock.get("skills", []) if e["agents"]]
    return lock


def entries_for(lock: dict[str, object], agent: str | None) -> list[dict[str, object]]:
    """The entries that describe `agent`'s skills directory.

    An entry without `agents` predates the field and counts for every agent.
    `None` means every entry.
    """
    return [
        entry for entry in lock.get("skills", [])
        if agent is None or "agents" not in entry or agent in entry["agents"]
    ]


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


def verify(target: Path, skills_dir: Path, agent: str | None = None) -> list[tuple[str, str, str]]:
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

    for entry in entries_for(lock, agent):
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
