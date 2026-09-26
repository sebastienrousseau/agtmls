# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Where the registry keeps its skills: one place to ask.

General skills, and bundles small enough to travel with them, live in
`skills/<name>/`. A bundle that is one project's knowledge rather than a
general skill lives in its own pack, `packs/<bundle>/skills/<name>/`, so the
default plugin (`./skills`) does not carry it and it installs as a plugin of
its own. The 14 noyalib skills were the first: every AgtMLS plugin install
used to list them, crowding Codex's skill budget for people who do not work
on noyalib.

Every script finds skills through here rather than globbing `skills/`, so a
pack cannot fall outside the index, the validators or the wheel.
"""

from __future__ import annotations

from pathlib import Path

GENERAL = "skills"
PACKS = "packs"


def skill_dirs(root: Path) -> list[Path]:
    """Every skill directory (one holding SKILL.md), sorted by skill name."""
    found = [p.parent for p in (root / GENERAL).glob("*/SKILL.md")]
    found += [p.parent for p in (root / PACKS).glob(f"*/{GENERAL}/*/SKILL.md")]
    return sorted(found, key=lambda path: (path.name, path.as_posix()))


def skill_files(root: Path) -> list[Path]:
    """Every SKILL.md, in skill_dirs order."""
    return [path / "SKILL.md" for path in skill_dirs(root)]


def find(root: Path, name: str) -> Path | None:
    """The directory of skill `name`, or None."""
    return next((path for path in skill_dirs(root) if path.name == name), None)


def pack_of(root: Path, skill_dir: Path) -> str | None:
    """The pack a skill directory sits in, or None for `skills/`."""
    rel = skill_dir.resolve().relative_to(root.resolve()).parts
    return rel[1] if rel[0] == PACKS else None


def packs(root: Path) -> list[str]:
    """Every pack that holds at least one skill."""
    return sorted({p.parents[2].name for p in (root / PACKS).glob(f"*/{GENERAL}/*/SKILL.md")})


def problems(root: Path, bundles: dict[str, str | None]) -> list[str]:
    """Layout rules: skill names unique across roots, and a pack holding only
    skills of its own bundle. `bundles` maps skill name to declared bundle."""
    errors = []
    seen: dict[str, Path] = {}
    for path in skill_dirs(root):
        rel = path.relative_to(root).as_posix()
        if path.name in seen:
            errors.append(f"skill {path.name} is in both {seen[path.name].relative_to(root).as_posix()} and {rel}")
        seen.setdefault(path.name, path)
        pack = pack_of(root, path)
        if pack is not None and bundles.get(path.name) != pack:
            errors.append(f"{rel} is in pack {pack} but declares bundle {bundles.get(path.name)!r}")
    return errors
