#!/usr/bin/env python3
"""Smoke-test skill scaffolding in a temporary output root."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "scripts" / "scaffold-skill.py"


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-scaffold-") as td:
        out_root = Path(td)
        proc = subprocess.run(
            [
                sys.executable,
                str(SCAFFOLD),
                "sample-skill",
                "--title",
                "Sample Skill",
                "--out-root",
                str(out_root),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if proc.returncode != 0:
            errors.append(f"scaffold failed:\n{proc.stdout}")
        expected = [
            out_root / "skills" / "sample-skill" / "SKILL.md",
            out_root / "skills" / "sample-skill" / "reference.md",
            out_root / "skills" / "sample-skill" / "metadata.json",
            out_root / "evals" / "cases" / "sample-skill.json",
            out_root / "evals" / "behavioral" / "cases" / "sample-skill.json",
        ]
        for path in expected:
            if not path.exists():
                errors.append(f"missing scaffolded file: {path}")
        skill = expected[0]
        if skill.exists():
            text = skill.read_text(encoding="utf-8")
            if "name: sample-skill" not in text or "# Sample Skill" not in text:
                errors.append("scaffolded SKILL.md did not replace placeholders")
        metadata = expected[2]
        if metadata.exists():
            try:
                json.loads(metadata.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"scaffolded metadata invalid JSON: {exc}")
        duplicate = subprocess.run(
            [sys.executable, str(SCAFFOLD), "sample-skill", "--out-root", str(out_root)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if duplicate.returncode == 0:
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
