#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Write each skill's chapter-10 attestations, or check they are current.

    python3 scripts/generate-skill-manifests.py --write
    python3 scripts/generate-skill-manifests.py --check

attestations/<skill>/manifest.intoto.json and capabilities.intoto.json,
outside the skill directory so they cannot move the digest they attest.
--check fails on any attestation that differs from its re-rendering, and on
any file under attestations/ that no current skill accounts for.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib.attestations import (  # noqa: E402  (needs the scripts path first)
    capabilities_statement,
    manifest_statement,
    render,
)

SKILLS_DIR = ROOT / "skills"
OUT = ROOT / "attestations"


def expected() -> dict[Path, str]:
    rendered: dict[Path, str] = {}
    for skill in sorted(p for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").exists()):
        rendered[OUT / skill.name / "manifest.intoto.json"] = render(manifest_statement(skill.name, skill))
        rendered[OUT / skill.name / "capabilities.intoto.json"] = render(capabilities_statement(skill.name, skill))
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        parser.print_help()
        return 2
    want = expected()
    if args.write:
        for path, text in want.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        print(f"wrote {len(want)} attestation(s) for {len(want) // 2} skill(s)")
        return 0
    errors = []
    for path, text in want.items():
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            errors.append(f"{path.relative_to(ROOT).as_posix()} is stale")
    present = set(OUT.rglob("*.json")) if OUT.exists() else set()
    for path in sorted(present - set(want)):
        errors.append(f"{path.relative_to(ROOT).as_posix()} belongs to no current skill")
    for error in errors:
        print(f"FAIL: {error}; run generate-skill-manifests.py --write")
    if errors:
        return 1
    print(f"OK: {len(want)} attestation(s) for {len(want) // 2} skill(s) are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
