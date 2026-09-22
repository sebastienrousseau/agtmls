# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A four-skill copy of the registry, for tests that must stay fast.

`registry_fixture` copies the whole tree, and on a machine where every file
copy costs milliseconds that is a second per TestCase class. The CLI and
installer tests only need a registry that is *real* -- genuine skills whose
digests match the index -- not one that is complete. So this copies four real
skills (two general, two bundled), their eval cases, and the files the
scripts read, and cuts index.json down to match. Nothing is synthesised: every
digest in the cut index is the one the generator wrote.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .support import ROOT

# Two general skills and two from different bundles, so bundle filters have
# something to keep and something to drop.
SKILLS = (
    "systematic-debugging",
    "using-agtmls",
    "noyalib-config-and-flags",
    "ai-supply-chain-security",
)
GENERAL = ("systematic-debugging", "using-agtmls")

_FILES = (
    "CATALOG.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE-APACHE",
    "LICENSE-MIT", "README.md", "RELEASE.md", "SECURITY.md", "checks.json",
    "profiles.json", "providers.json",
)
_DIRS = (".claude-plugin", "agents", "commands", "system-prompts", "templates", "scripts/_lib")


def mini_registry(destination: Path) -> Path:
    """Build the cut-down registry at `destination` and return its resolved root."""
    destination.mkdir(parents=True, exist_ok=True)
    # Resolved for the same reason registry_fixture resolves: /var vs /private/var.
    destination = destination.resolve()
    ignore = shutil.ignore_patterns("__pycache__")
    for name in _FILES:
        shutil.copy2(ROOT / name, destination / name)
    for name in _DIRS:
        shutil.copytree(ROOT / name, destination / name, ignore=ignore)
    # import-skill.py audits through this script as a subprocess.
    shutil.copy2(ROOT / "scripts" / "audit-skill.py", destination / "scripts" / "audit-skill.py")
    for name in SKILLS:
        shutil.copytree(ROOT / "skills" / name, destination / "skills" / name, ignore=ignore)
        for cases in ("evals/cases", "evals/behavioral/cases"):
            (destination / cases).mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / cases / f"{name}.json", destination / cases / f"{name}.json")

    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    index["skills"] = [skill for skill in index["skills"] if skill["name"] in SKILLS]
    index["skill_count"] = len(index["skills"])
    bundles: dict[str, int] = {}
    for skill in index["skills"]:
        key = skill["bundle"] or "_general"
        bundles[key] = bundles.get(key, 0) + 1
    index["bundles"] = bundles
    (destination / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return destination


def replace_file(case, path: Path, text: str | None) -> None:
    """Rewrite (or, with None, delete) a fixture file for one test only.

    The fixture is built once per class, so a test that breaks it must put it
    back or every later test inherits the damage.
    """
    original = path.read_bytes() if path.exists() else None

    def restore() -> None:
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)

    case.addCleanup(restore)
    if text is None:
        path.unlink()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
