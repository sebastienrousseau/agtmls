# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The steps of `agtmls uninstall` that touch the agent's directory.

Each removes only what the registry put there: a link into it, a copy the
lockfile records with its digest unchanged, or a file byte-identical to the
registry's. scripts/agtmls.py runs them in order and settles the lockfile.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from _lib import lockfile


def remove_registry_links(base: Path, root: Path, touched: set[str]) -> int:
    """Links into the registry at `root` under the agent's skills, commands and
    agents directories; `touched` gains each directory something left."""
    removed = 0
    for sub in ["skills", "commands", "agents"]:
        directory = base / sub
        if not directory.exists():
            continue
        for entry in directory.iterdir():
            if not entry.is_symlink():
                continue
            try:
                resolved = entry.resolve(strict=True)
            except FileNotFoundError:
                continue
            # A string prefix would also match a sibling checkout whose
            # path merely starts with ours, e.g. ../agtmls-experiments.
            if resolved.is_relative_to(root):
                entry.unlink()
                removed += 1
                touched.add(sub)
    return removed


def remove_recorded_copies(lock: dict, agent: str, skills_dir: Path, kept: set[str], touched: set[str]) -> int:
    """This agent's copied skills, as the lockfile records them. A skill
    whose digest moved is a local edit: it is left, and named in `kept`."""
    from _lib.digest import skill_digest

    removed = 0
    for entry in lockfile.entries_for(lock, agent):
        installed = skills_dir / entry.get("path", entry["name"])
        if installed.is_symlink() or not installed.is_dir():
            continue
        if skill_digest(installed) != entry["integrity"]:
            print(f"   {entry['name']}: modified since install; left in place")
            kept.add(entry["name"])
            continue
        shutil.rmtree(installed)
        removed += 1
        touched.add("skills")
    return removed


def remove_copied_files(base: Path, root: Path, touched: set[str]) -> int:
    """Copied commands and agents that still equal those of the registry at `root`."""
    removed = 0
    for sub in ["commands", "agents"]:
        directory = base / sub
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            source = root / sub / entry.name
            if (entry.is_file() and not entry.is_symlink() and source.is_file()
                    and entry.read_bytes() == source.read_bytes()):
                entry.unlink()
                removed += 1
                touched.add(sub)
    return removed


def prune_empty(base: Path, touched: set[str]) -> None:
    """Directories the uninstall emptied, then the agent directory itself."""
    for directory in [base / sub for sub in sorted(touched)] + ([base] if touched else []):
        try:
            directory.rmdir()
        except OSError:
            pass  # not empty: something in it is not ours
