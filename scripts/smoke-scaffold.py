#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Smoke-test skill scaffolding in a temporary output root."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "scripts" / "scaffold-skill.py"


def scaffold(out_root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCAFFOLD), "sample-skill", *extra, "--out-root", str(out_root)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def skill_problems(skill: Path) -> list[str]:
    """The scaffolded SKILL.md has its placeholders replaced."""
    try:
        text = skill.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ["scaffolded SKILL.md is not UTF-8 text"]
    if "name: sample-skill" not in text or "# Sample Skill" not in text:
        return ["scaffolded SKILL.md did not replace placeholders"]
    return []


def scaffolded_problems(out_root: Path) -> list[str]:
    """Every file a scaffold promises exists, with its placeholders replaced."""
    expected = [
        out_root / "skills" / "sample-skill" / "SKILL.md",
        out_root / "skills" / "sample-skill" / "reference.md",
        out_root / "skills" / "sample-skill" / "metadata.json",
        out_root / "evals" / "cases" / "sample-skill.json",
        out_root / "evals" / "behavioral" / "cases" / "sample-skill.json",
    ]
    errors = [f"missing scaffolded file: {path}" for path in expected if not path.exists()]
    skill, metadata = expected[0], expected[2]
    if skill.exists():
        errors += skill_problems(skill)
    if metadata.exists():
        try:
            json.loads(metadata.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"scaffolded metadata invalid JSON: {exc}")
    return errors


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-scaffold-") as td:
        out_root = Path(td)
        proc = scaffold(out_root, "--title", "Sample Skill")
        if proc.returncode != 0:
            errors.append(f"scaffold failed:\n{proc.stdout}")
        errors += scaffolded_problems(out_root)
        if scaffold(out_root).returncode == 0:
            errors.append("duplicate scaffold should fail")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} scaffold smoke issue(s)")
        return 1
    print("OK: scaffold smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
