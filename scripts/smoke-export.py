#!/usr/bin/env python3
"""Smoke-test provider-neutral export bundles."""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-export-smoke-") as td:
        out_dir = Path(td)
        proc = subprocess.run([sys.executable, str(CLI), "export", "--provider", "openai", "--profile", "polyglot", "--out-dir", str(out_dir)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        if proc.returncode != 0:
            errors.append(f"export command failed:\n{proc.stdout}")
        archives = sorted(out_dir.glob("*.tar.gz"))
        if len(archives) != 1:
            errors.append(f"expected one archive, found {len(archives)}")
        elif tarfile.is_tarfile(archives[0]):
            with tarfile.open(archives[0], "r:gz") as tf:
                names = set(tf.getnames())
                if "agtmls/export-manifest.json" not in names:
                    errors.append("archive missing export-manifest.json")
                if "agtmls/skills/cross-language-port/SKILL.md" not in names:
                    errors.append("archive missing cross-language-port skill")
                member = tf.extractfile("agtmls/export-manifest.json")
                if member is None:
                    errors.append("cannot read export manifest")
                else:
                    payload = json.loads(member.read().decode("utf-8"))
                    if payload.get("provider") != "openai" or payload.get("profile") != "polyglot":
                        errors.append(f"wrong export manifest: {payload}")
        else:
            errors.append("export did not produce a valid tar.gz")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} export smoke issue(s)")
        return 1
    print("OK: export smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
