#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate the PyPI packaging surface.

`uvx agtmls` ships the registry inside the wheel under `agtmls/_registry/`.
That layout is load-bearing: every script resolves its root as
`Path(__file__).resolve().parent.parent`, so scripts must land at
`agtmls/_registry/scripts/` for the registry root to resolve. The failure
mode this guards is silent — a wheel that installs fine and then cannot find
skills, profiles, or the installer at runtime.

Checks, without importing a TOML parser on older Pythons:
  - every runtime-required path is force-included, and mapped under
    agtmls/_registry/ with its name preserved;
  - no force-included source path is missing from the working tree;
  - the sdist carries every file the wheel build reads, because the release
    builds its wheel from the sdist, never from the tree;
  - the pyproject version matches plugin.json and src/agtmls/__init__.py;
  - the console script points at the real entry point.
"""

from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

try:  # 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 only
    tomllib = None  # type: ignore[assignment]  # 3.10 has no tomllib; guarded at every use

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
INIT = ROOT / "src" / "agtmls" / "__init__.py"
ENTRY_POINT = "agtmls.cli:main"

# Everything the packaged CLI touches at runtime. `agtmls install` shells out
# to setup-workspace.sh, which reads system-prompts/ and skills/; list/search/
# show/stats read index.json; export reads profiles.json and providers.json.
REQUIRED = [
    "scripts",
    "skills",
    "commands",
    "agents",
    "system-prompts",
    "references",
    "templates",
    "index.json",
    "profiles.json",
    "providers.json",
]
PREFIX = "agtmls/_registry"


def parse_force_include(text: str) -> dict[str, str]:
    """Read the force-include table without tomllib, for 3.10 support."""
    section = re.search(
        r"^\[tool\.hatch\.build\.targets\.wheel\.force-include\]\s*$(.*?)(?=^\[|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not section:
        return {}
    pairs = {}
    for line in section.group(1).splitlines():
        line = line.split("#", 1)[0].strip()
        match = re.match(r'^"([^"]+)"\s*=\s*"([^"]+)"$', line)
        if match:
            pairs[match.group(1)] = match.group(2)
    return pairs


def _section(text: str, name: str) -> str:
    match = re.search(
        rf"^\[{re.escape(name)}\]\s*$(.*?)(?=^\[|\Z)", text, re.MULTILINE | re.DOTALL
    )
    return match.group(1) if match else ""


def parse_project(text: str) -> dict:
    """The [project] fields this check reads, without tomllib, for 3.10.

    Without it, 3.10 skipped the name, console-script and no-dependencies
    checks and still reported OK, so one leg of the CI matrix ran a weaker
    gate than the others.
    """
    project = _section(text, "project")

    def string(key: str) -> str:
        match = re.search(rf'^{key}\s*=\s*"([^"]*)"', project, re.MULTILINE)
        return match.group(1) if match else ""

    deps = re.search(r"^dependencies\s*=\s*\[(.*?)\]", project, re.MULTILINE | re.DOTALL)
    scripts = {
        match.group(1): match.group(2)
        for match in re.finditer(r'^([\w.-]+)\s*=\s*"([^"]*)"', _section(text, "project.scripts"), re.MULTILINE)
    }
    return {
        "name": string("name"),
        "version": string("version"),
        "scripts": scripts,
        "dependencies": re.findall(r'"([^"]*)"', deps.group(1)) if deps else [],
    }


# The build hook, and the file it adds to the wheel when CI has made one.
HOOK = "hatch_build.py"
SIGNATURE = "index.json.sig"


def _string_array(section: str, key: str) -> list[str]:
    match = re.search(rf"^{key}\s*=\s*\[(.*?)\]", section, re.MULTILINE | re.DOTALL)
    return re.findall(r'"([^"]*)"', match.group(1)) if match else []


def _in_sdist(path: str, include: list[str]) -> bool:
    return any(
        path == pattern or path.startswith(f"{pattern}/") or fnmatch.fnmatchcase(path, pattern)
        for pattern in include
    )


def sdist_gaps(text: str) -> list[str]:
    """Files the wheel build reads that a wheel built from the sdist would lack.

    `python -m build` builds the sdist, unpacks it and builds the wheel from
    that, so a force-include source, the build hook or the signature the hook
    adds must each be in the sdist. The signature is gitignored, and hatch
    leaves gitignored files out of an sdist unless they are artifacts.
    """
    sdist = _section(text, "tool.hatch.build.targets.sdist")
    include = _string_array(sdist, "include")
    gaps = [
        f"the sdist omits {source}, which the wheel force-includes"
        for source in parse_force_include(text)
        if not _in_sdist(source, include)
    ]
    if re.search(r"^\[tool\.hatch\.build\.targets\.wheel\.hooks\.custom\]", text, re.MULTILINE):
        if not _in_sdist(HOOK, include):
            gaps.append(f"the sdist omits {HOOK}, the wheel's build hook")
        if not _in_sdist(SIGNATURE, include):
            gaps.append(f"the sdist omits {SIGNATURE}, which the build hook ships")
        if SIGNATURE not in _string_array(sdist, "artifacts"):
            gaps.append(f"the sdist must list {SIGNATURE} under artifacts: it is gitignored")
    return gaps


def main() -> int:
    errors: list[str] = []
    if not PYPROJECT.exists():
        print("FAIL: pyproject.toml missing")
        return 1
    text = PYPROJECT.read_text(encoding="utf-8")

    if tomllib is not None:
        data = tomllib.loads(text)
        project = data.get("project", {})
        include = (
            data.get("tool", {})
            .get("hatch", {})
            .get("build", {})
            .get("targets", {})
            .get("wheel", {})
            .get("force-include", {})
        )
    else:
        project = parse_project(text)
        include = parse_force_include(text)
    version = str(project.get("version", ""))
    if project.get("name") != "agtmls":
        errors.append("pyproject project.name must be agtmls")
    if project.get("scripts", {}).get("agtmls") != ENTRY_POINT:
        errors.append(f"console script agtmls must be {ENTRY_POINT}")
    if project.get("dependencies"):
        errors.append("registry scripts are stdlib-only; dependencies must stay empty")

    for rel in REQUIRED:
        if rel not in include:
            errors.append(f"force-include missing runtime path: {rel}")
            continue
        target = include[rel]
        expected = f"{PREFIX}/{rel}"
        if target != expected:
            errors.append(f"force-include {rel} maps to {target}, expected {expected}")

    for source, target in include.items():
        if not (ROOT / source).exists():
            errors.append(f"force-include source does not exist: {source}")
        if not target.startswith(f"{PREFIX}/"):
            errors.append(f"force-include target must live under {PREFIX}/: {target}")

    errors += sdist_gaps(text)

    plugin_version = str(json.loads(PLUGIN.read_text(encoding="utf-8")).get("version", ""))
    if version != plugin_version:
        errors.append(f"pyproject version {version} must match plugin.json {plugin_version}")

    if INIT.exists():
        match = re.search(r'^__version__\s*=\s*"([^"]+)"', INIT.read_text(encoding="utf-8"), re.MULTILINE)
        if not match:
            errors.append("src/agtmls/__init__.py must define __version__")
        elif match.group(1) != plugin_version:
            errors.append(
                f"__version__ {match.group(1)} must match plugin.json {plugin_version}"
            )
    else:
        errors.append("src/agtmls/__init__.py missing")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} packaging issue(s)")
        return 1
    print(f"OK: packaging valid, {len(include)} path(s) bundled into {PREFIX}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
