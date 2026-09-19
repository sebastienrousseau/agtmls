#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Prove install-time integrity verification actually refuses bad input.

A digest that nothing checks is a number in a JSON file. These properties are
what make it a control:

  * a registry that no longer matches index.json cannot be installed;
  * a refusal installs nothing at all, rather than copying and then reporting;
  * an installed tree records what it installed and what it hashed to;
  * modification and deletion of an installed skill are both detected;
  * a skill the lockfile does not know about is reported, never deleted.

Spec: agtmls-spec/spec/06-lockfile.md.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"
EXIT_INTEGRITY_FAILURE = 3


def agtmls(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )


def fresh(tmp: Path, name: str) -> Path:
    target = tmp / name
    target.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    return target


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-verify-") as raw:
        tmp = Path(raw)

        # 1. A clean install records a lockfile covering what it installed.
        target = fresh(tmp, "clean")
        proc = agtmls("install", "rust", "claude", "--target", str(target), "--copy")
        if proc.returncode != 0:
            print(f"FAIL: install failed:\n{proc.stdout}")
            return 1
        lock_path = target / ".agtmls" / "manifest.json"
        if not lock_path.exists():
            errors.append("install wrote no lockfile")
        else:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            installed = sorted(p.name for p in (target / ".claude" / "skills").iterdir())
            recorded = sorted(entry["name"] for entry in lock["skills"])
            if installed != recorded:
                errors.append(f"lockfile records {recorded}, installed {installed}")
            if not all(e["integrity"].startswith("sha256:") for e in lock["skills"]):
                errors.append("lockfile entries lack a sha256 digest")

        # 2. A clean tree verifies.
        proc = agtmls("verify", "claude", "--target", str(target))
        if proc.returncode != 0:
            errors.append(f"clean tree failed verification:\n{proc.stdout}")

        # 3. Modifying an installed skill is detected.
        victim = next((target / ".claude" / "skills").iterdir())
        (victim / "SKILL.md").write_text("tampered\n", encoding="utf-8")
        proc = agtmls("verify", "claude", "--target", str(target))
        if proc.returncode != EXIT_INTEGRITY_FAILURE:
            errors.append(f"modified skill: expected exit {EXIT_INTEGRITY_FAILURE}, got {proc.returncode}")
        if "MODIFIED" not in proc.stdout:
            errors.append(f"modified skill not reported:\n{proc.stdout}")

        # 4. Deleting an installed skill is detected.
        shutil.rmtree(victim)
        proc = agtmls("verify", "claude", "--target", str(target))
        if "MISSING" not in proc.stdout:
            errors.append(f"deleted skill not reported:\n{proc.stdout}")

        # 5. An unmanaged skill is reported but not an integrity failure, and
        #    must never be removed: deleting what we did not install is not ours
        #    to do.
        target = fresh(tmp, "unmanaged")
        agtmls("install", "rust", "claude", "--target", str(target), "--copy")
        stranger = target / ".claude" / "skills" / "not-ours"
        stranger.mkdir()
        (stranger / "SKILL.md").write_text("mine\n", encoding="utf-8")
        proc = agtmls("verify", "claude", "--target", str(target), "--json")
        payload = json.loads(proc.stdout)
        statuses = {p["skill"]: p["status"] for p in payload["problems"]}
        if statuses.get("not-ours") != "unmanaged":
            errors.append(f"unmanaged skill not reported: {payload}")
        if proc.returncode != 0:
            errors.append(f"unmanaged-only tree should not be an integrity failure, got {proc.returncode}")
        if not stranger.exists():
            errors.append("verify deleted a skill it did not install")

        # 6. A registry that no longer matches index.json cannot be installed,
        #    and the refusal installs nothing.
        backup = None
        drifted = ROOT / "skills" / "writing-plans" / "SKILL.md"
        try:
            backup = drifted.read_text(encoding="utf-8")
            drifted.write_text(backup + "\ndrifted\n", encoding="utf-8")
            target = fresh(tmp, "drift")
            proc = agtmls("install", "rust", "claude", "--target", str(target), "--copy")
            if proc.returncode != EXIT_INTEGRITY_FAILURE:
                errors.append(
                    f"drifted registry: expected exit {EXIT_INTEGRITY_FAILURE}, got {proc.returncode}"
                )
            if (target / ".claude" / "skills").exists():
                errors.append("drifted registry install copied skills before refusing")
        finally:
            if backup is not None:
                drifted.write_text(backup, encoding="utf-8")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} install-verification issue(s)")
        return 1
    print("OK: install verification and lockfile hold (6 properties)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
