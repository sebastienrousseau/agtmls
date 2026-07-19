#!/usr/bin/env python3
"""Smoke-test provider-adapted export bundles."""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"
CASES = [
    ("openai", "polyglot", "agtmls/adapters/openai/AGENTS.md"),
    ("github-copilot", "minimal", "agtmls/adapters/github-copilot/.github/copilot-instructions.md"),
    ("cursor", "polyglot", "agtmls/adapters/cursor/.cursor/rules/agtmls.mdc"),
    ("continue", "minimal", "agtmls/adapters/continue/.continue/rules/agtmls.md"),
]


def check_archive(provider: str, profile: str, adapter: str, out_dir: Path, errors: list[str]) -> None:
    proc = subprocess.run([sys.executable, str(CLI), "export", "--provider", provider, "--profile", profile, "--out-dir", str(out_dir)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if proc.returncode != 0:
        errors.append(f"export {provider}/{profile} failed:\n{proc.stdout}")
        return
    archive = out_dir / f"agtmls-{provider}-{profile}.tar.gz"
    if not archive.exists() or not tarfile.is_tarfile(archive):
        errors.append(f"missing or invalid archive: {archive}")
        return
    with tarfile.open(archive, "r:gz") as tf:
        names = set(tf.getnames())
        for required in ["agtmls/export-manifest.json", "agtmls/ADAPTERS.md", adapter]:
            if required not in names:
                errors.append(f"{provider}/{profile} archive missing {required}")
        if "agtmls/skills/using-agtmls/SKILL.md" not in names:
            errors.append(f"{provider}/{profile} archive missing using-agtmls")
        member = tf.extractfile("agtmls/export-manifest.json")
        if member is None:
            errors.append(f"{provider}/{profile} cannot read export manifest")
            return
        payload = json.loads(member.read().decode("utf-8"))
        if payload.get("provider") != provider or payload.get("profile") != profile:
            errors.append(f"wrong export manifest: {payload}")
        if adapter.replace("agtmls/", "") not in payload.get("adapter_files", []):
            errors.append(f"manifest missing adapter file {adapter}: {payload}")


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-export-smoke-") as td:
        out_dir = Path(td)
        for provider, profile, adapter in CASES:
            check_archive(provider, profile, adapter, out_dir, errors)
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
