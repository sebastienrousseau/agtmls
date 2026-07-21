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


def provider_count() -> int:
    data = json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
    return len(data.get("export_targets", {}))


def run_pack(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def validate_manifest(out_dir: Path, profile: str, expected_count: int, errors: list[str]) -> None:
    manifest = out_dir / "release-manifest.json"
    sums = out_dir / "SHA256SUMS"
    if not manifest.exists():
        errors.append("release manifest missing")
        return
    data = json.loads(manifest.read_text(encoding="utf-8"))
    artifacts = data.get("artifacts", [])
    if data.get("profile") != profile or len(artifacts) != expected_count:
        errors.append(f"release manifest wrong: {data}")
    if not sums.exists() or len(sums.read_text(encoding="utf-8").splitlines()) != expected_count:
        errors.append("SHA256SUMS missing or wrong line count")
    for item in artifacts:
        name = item.get("file") if isinstance(item, dict) else None
        if not name or not (out_dir / name).exists():
            errors.append(f"release artifact missing: {name}")


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-release-pack-") as td:
        root = Path(td)
        selected_dir = root / "selected"
        selected = run_pack(["--out-dir", str(selected_dir), "--profile", "minimal", "--provider", "generic", "--provider", "openai"])
        if selected.returncode != 0:
            errors.append(f"selected release-pack failed:\n{selected.stdout}")
        validate_manifest(selected_dir, "minimal", 2, errors)

        all_dir = root / "all"
        all_providers = run_pack(["--out-dir", str(all_dir), "--profile", "minimal"])
        if all_providers.returncode != 0:
            errors.append(f"all-provider release-pack failed:\n{all_providers.stdout}")
        validate_manifest(all_dir, "minimal", provider_count(), errors)
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
