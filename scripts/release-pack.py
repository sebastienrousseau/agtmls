#!/usr/bin/env python3
"""Build release artifacts and checksums for AgtMLS."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORT = ROOT / "scripts" / "export-registry.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist" / "release")
    parser.add_argument("--profile", default="polyglot")
    parser.add_argument("--provider", action="append", default=None)
    args = parser.parse_args()
    providers = args.provider or ["generic", "openai", "anthropic", "cursor", "github-copilot", "continue"]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[Path] = []
    for provider in providers:
        cmd = [sys.executable, str(EXPORT), "--provider", provider, "--profile", args.profile, "--out-dir", str(args.out_dir)]
        rc = subprocess.call(cmd, cwd=ROOT)
        if rc != 0:
            return rc
        artifacts.append(args.out_dir / f"agtmls-{provider}-{args.profile}.tar.gz")
    lines = []
    manifest: dict[str, object] = {"schema_version": 1, "profile": args.profile, "artifacts": []}
    for artifact in sorted(artifacts):
        digest = sha256(artifact)
        lines.append(f"{digest}  {artifact.name}")
        manifest["artifacts"].append({"file": artifact.name, "sha256": digest})
    (args.out_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (args.out_dir / "release-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
