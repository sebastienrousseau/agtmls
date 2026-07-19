#!/usr/bin/env python3
"""Smoke-test release artifact packaging."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "release-pack.py"


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-release-pack-") as td:
        out_dir = Path(td) / "release"
        proc = subprocess.run([sys.executable, str(SCRIPT), "--out-dir", str(out_dir), "--profile", "minimal", "--provider", "generic", "--provider", "openai"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        if proc.returncode != 0:
            errors.append(f"release-pack failed:\n{proc.stdout}")
        manifest = out_dir / "release-manifest.json"
        sums = out_dir / "SHA256SUMS"
        if not manifest.exists():
            errors.append("release manifest missing")
        else:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("profile") != "minimal" or len(data.get("artifacts", [])) != 2:
                errors.append(f"release manifest wrong: {data}")
        if not sums.exists() or len(sums.read_text(encoding="utf-8").splitlines()) != 2:
            errors.append("SHA256SUMS missing or wrong line count")
        for name in ["agtmls-generic-minimal.tar.gz", "agtmls-openai-minimal.tar.gz"]:
            if not (out_dir / name).exists():
                errors.append(f"release artifact missing: {name}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} release pack smoke issue(s)")
        return 1
    print("OK: release pack smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
