#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate every skill with the Agent Skills *reference* implementation.

`validate-skills.py` enforces our reading of the spec plus the stricter AgtMLS
router contract. This check enforces the spec itself, using `skills-ref` from
the agentskills project — the tool other publishers validate against. The two
can disagree, and when they do the reference implementation wins.

The dependency is optional so the gate stays runnable on a machine with no
network: locally, if `agentskills` is not importable, this reports SKIP and
exits 0. In CI (`CI` set) a missing validator is a FAIL on every Python the
reference supports (3.11+): it used to SKIP there too, and CI installed it
with `|| true`, so one failed install turned the spec check off unnoticed.

    pip install skills-ref
    python3 scripts/validate-spec-conformance.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
# skills-ref declares requires-python >= 3.11.
REFERENCE_FLOOR = (3, 11)
PYTHON = sys.version_info[:2]


def runner() -> list[str] | None:
    """The reference CLI, however it is reachable."""
    found = shutil.which("agentskills")
    if found:
        return [found]
    probe = subprocess.run(
        [sys.executable, "-c", "import skills_ref"],
        capture_output=True,
        check=False,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "skills_ref.cli"]
    return None


def main() -> int:
    cmd = runner()
    if cmd is None:
        if os.environ.get("CI") and PYTHON >= REFERENCE_FLOOR:
            print("FAIL: skills-ref is not installed, and CI must run the spec check on Python 3.11+")
            return 1
        reason = "Python < 3.11" if PYTHON < REFERENCE_FLOOR else "pip install skills-ref"
        print(f"SKIP: skills-ref is not available ({reason}); spec check not run")
        return 0

    skills = sorted(p.parent for p in SKILLS_DIR.glob("*/SKILL.md"))
    if not skills:
        print(f"FAIL: no skills found under {SKILLS_DIR}")
        return 1

    failures = 0
    for skill in skills:
        proc = subprocess.run(
            [*cmd, "validate", str(skill)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        if proc.returncode != 0:
            failures += 1
            print(f"FAIL: {skill.relative_to(ROOT)}")
            for line in (proc.stdout + proc.stderr).strip().splitlines():
                print(f"    {line}")

    if failures:
        print()
        print(f"FAIL: {failures} skill(s) rejected by the reference implementation")
        return 1
    print(f"OK: {len(skills)} skill(s) valid per skills-ref")
    return 0


if __name__ == "__main__":
    sys.exit(main())
