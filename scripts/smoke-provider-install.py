#!/usr/bin/env python3
"""Smoke-test provider adapter installation for every export target."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def providers() -> list[str]:
    data = json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
    return sorted(data.get("export_targets", {}))


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-provider-") as td:
        target = Path(td)
        for provider in providers():
            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "provider-install.py"),
                "--provider",
                provider,
                "--target",
                str(target),
                "--profile",
                "polyglot",
            ]
            proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
            if proc.returncode:
                errors.append(f"install {provider} failed:\n{proc.stdout}")
                continue
            check = subprocess.run([*cmd, "--check"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
            if check.returncode:
                errors.append(f"check {provider} failed:\n{check.stdout}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} provider install smoke issue(s)")
        return 1
    print(f"OK: provider install smoke test passed for {len(providers())} provider(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
