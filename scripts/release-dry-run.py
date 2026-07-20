#!/usr/bin/env python3
"""Run a release dry-run without publishing tags or GitHub releases."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> int:
    print("$ " + " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sums(out_dir: Path) -> list[str]:
    errors: list[str] = []
    sums = out_dir / "SHA256SUMS"
    manifest = out_dir / "release-manifest.json"
    if not sums.exists():
        return ["SHA256SUMS missing"]
    if not manifest.exists():
        errors.append("release-manifest.json missing")
    for line in sums.read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        artifact = out_dir / name.strip()
        if not artifact.exists():
            errors.append(f"artifact listed in SHA256SUMS is missing: {name}")
            continue
        actual = sha256(artifact)
        if actual != expected:
            errors.append(f"checksum mismatch for {name}: {actual} != {expected}")
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        listed = {item["file"] for item in data.get("artifacts", [])}
        summed = {line.split(maxsplit=1)[1].strip() for line in sums.read_text(encoding="utf-8").splitlines()}
        if listed != summed:
            errors.append("release manifest artifact list does not match SHA256SUMS")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="expected release version; defaults to current registry version")
    parser.add_argument("--skip-check", action="store_true", help="skip the full agtmls check gate")
    parser.add_argument("--profile", default="minimal")
    parser.add_argument("--provider", action="append", default=None)
    args = parser.parse_args()

    version = args.version or json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    next_proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "next-version.py")], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if next_proc.returncode != 0:
        print(next_proc.stderr or next_proc.stdout, file=sys.stderr)
        return next_proc.returncode
    next_version = next_proc.stdout.strip()
    tag_proc = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"refs/tags/v{version}"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if version != next_version and tag_proc.returncode != 0:
        print(f"FAIL: requested {version}; next allowed release is {next_version}")
        return 1

    checks = [[sys.executable, str(ROOT / "scripts" / "validate-version-policy.py")], [sys.executable, str(ROOT / "scripts" / "release-check.py")]]
    if not args.skip_check:
        checks.insert(0, [sys.executable, str(ROOT / "scripts" / "run-all-checks.py")])
    for cmd in checks:
        rc = run(cmd)
        if rc != 0:
            return rc

    providers = args.provider or ["generic", "openai"]
    with tempfile.TemporaryDirectory(prefix="agtmls-release-dry-run-") as td:
        out_dir = Path(td) / "release"
        pack_cmd = [sys.executable, str(ROOT / "scripts" / "release-pack.py"), "--out-dir", str(out_dir), "--profile", args.profile]
        for provider in providers:
            pack_cmd.extend(["--provider", provider])
        rc = run(pack_cmd)
        if rc != 0:
            return rc
        errors = verify_sums(out_dir)
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            print()
            print(f"FAIL: {len(errors)} release dry-run issue(s)")
            return 1
        print(f"OK: release dry-run passed for {version} with {len(providers)} artifact(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
