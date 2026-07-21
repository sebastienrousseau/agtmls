#!/usr/bin/env python3
"""Smoke-test provider-adapted export bundles for every configured provider."""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"


def cases() -> list[tuple[str, str, list[str]]]:
    data = json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
    items = []
    for provider, spec in sorted(data.get("export_targets", {}).items()):
        profile = "minimal" if provider in {"continue", "github-copilot", "generic"} else "polyglot"
        adapters = [f"agtmls/{path}" for path in spec.get("adapter_files", [])]
        items.append((provider, profile, adapters))
    return items


def check_archive(provider: str, profile: str, adapters: list[str], out_dir: Path, errors: list[str]) -> None:
    proc = subprocess.run(
        [sys.executable, str(CLI), "export", "--provider", provider, "--profile", profile, "--out-dir", str(out_dir)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        errors.append(f"export {provider}/{profile} failed:\n{proc.stdout}")
        return
    archive = out_dir / f"agtmls-{provider}-{profile}.tar.gz"
    if not archive.exists() or not tarfile.is_tarfile(archive):
        errors.append(f"missing or invalid archive: {archive}")
        return
    with tarfile.open(archive, "r:gz") as tf:
        names = set(tf.getnames())
        for required in ["agtmls/export-manifest.json", "agtmls/ADAPTERS.md", *adapters]:
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
        expected = [adapter.replace("agtmls/", "") for adapter in adapters]
        for adapter in expected:
            if adapter not in payload.get("adapter_files", []):
                errors.append(f"manifest missing adapter file {adapter}: {payload}")


def main() -> int:
    errors: list[str] = []
    all_cases = cases()
    with tempfile.TemporaryDirectory(prefix="agtmls-export-smoke-") as td:
        out_dir = Path(td)
        for provider, profile, adapters in all_cases:
            check_archive(provider, profile, adapters, out_dir, errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} export smoke issue(s)")
        return 1
    print(f"OK: export smoke test passed for {len(all_cases)} provider(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
