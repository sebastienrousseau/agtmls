#!/usr/bin/env python3
"""Download a GitHub release and verify its checksums and tarball manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO = "sebastienrousseau/agtmls"
ASSETS = [
    "agtmls-anthropic-polyglot.tar.gz",
    "agtmls-continue-polyglot.tar.gz",
    "agtmls-cursor-polyglot.tar.gz",
    "agtmls-generic-polyglot.tar.gz",
    "agtmls-github-copilot-polyglot.tar.gz",
    "agtmls-openai-polyglot.tar.gz",
    "release-manifest.json",
    "SHA256SUMS",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, path: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        path.write_bytes(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="v0.0.1")
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    base = f"https://github.com/{args.repo}/releases/download/{args.tag}"
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-release-assets-") as td:
        out_dir = args.out_dir or Path(td)
        out_dir.mkdir(parents=True, exist_ok=True)
        gh = shutil.which("gh")
        if gh:
            proc = subprocess.run([gh, "release", "download", args.tag, "--repo", args.repo, "--dir", str(out_dir), "--clobber"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
            if proc.returncode != 0:
                print(proc.stdout, end="")
                return proc.returncode
        else:
            for name in ASSETS:
                download(f"{base}/{name}", out_dir / name)
        missing = [name for name in ASSETS if not (out_dir / name).exists()]
        if missing:
            for name in missing:
                print(f"FAIL: release asset missing after download: {name}")
            print()
            print(f"FAIL: {len(missing)} release asset issue(s)")
            return 1
        sums = {}
        for line in (out_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, name = line.split(maxsplit=1)
            sums[name.strip()] = digest
        manifest = json.loads((out_dir / "release-manifest.json").read_text(encoding="utf-8"))
        for item in manifest.get("artifacts", []):
            name = item["file"]
            artifact = out_dir / name
            if not artifact.exists():
                errors.append(f"manifest artifact missing: {name}")
                continue
            actual = sha256(artifact)
            if sums.get(name) != actual:
                errors.append(f"SHA256SUMS mismatch for {name}")
            if item.get("sha256") != actual:
                errors.append(f"release-manifest checksum mismatch for {name}")
            try:
                with tarfile.open(artifact, "r:gz") as tf:
                    names = set(tf.getnames())
            except tarfile.TarError as exc:
                errors.append(f"invalid tarball {name}: {exc}")
                continue
            for required in ["agtmls/index.json", "agtmls/export-manifest.json", "agtmls/ADAPTERS.md"]:
                if required not in names:
                    errors.append(f"{name} missing {required}")
        for name, expected in sums.items():
            if name == "SHA256SUMS":
                continue
            path = out_dir / name
            if path.exists() and sha256(path) != expected:
                errors.append(f"checksum mismatch for {name}")
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            print()
            print(f"FAIL: {len(errors)} release asset issue(s)")
            return 1
        print(f"OK: verified {args.repo} {args.tag} release assets in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
