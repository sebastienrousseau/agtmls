#!/usr/bin/env python3
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
  - the pyproject version matches plugin.json and src/agtmls/__init__.py;
  - the console script points at the real entry point.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:  # 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 only
    tomllib = None  # type: ignore[assignment]

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


def main() -> int:
    errors: list[str] = []
    if not PYPROJECT.exists():
        print("FAIL: pyproject.toml missing")
        return 1
    text = PYPROJECT.read_text(encoding="utf-8")

    if tomllib is not None:
        data = tomllib.loads(text)
        project = data.get("project", {})
        version = str(project.get("version", ""))
        scripts = project.get("scripts", {})
        include = (
            data.get("tool", {})
            .get("hatch", {})
            .get("build", {})
            .get("targets", {})
            .get("wheel", {})
            .get("force-include", {})
        )
        if project.get("name") != "agtmls":
            errors.append("pyproject project.name must be agtmls")
        if scripts.get("agtmls") != ENTRY_POINT:
            errors.append(f"console script agtmls must be {ENTRY_POINT}")
        if project.get("dependencies"):
            errors.append("registry scripts are stdlib-only; dependencies must stay empty")
    else:  # pragma: no cover
        include = parse_force_include(text)
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        version = match.group(1) if match else ""

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

    plugin_version = str(json.loads(PLUGIN.read_text(encoding="utf-8")).get("version", ""))
    if version != plugin_version:
        errors.append(f"pyproject version {version} must match plugin.json {plugin_version}")

    if INIT.exists():
        match = re.search(r'^__version__\s*=\s*"([^"]+)"', INIT.read_text(encoding="utf-8"), re.M)
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
