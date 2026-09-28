#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Download a GitHub release and verify its checksums and tarball manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.checksums import parse_sums  # needs the scripts path first

REPO = "sebastienrousseau/agtmls"
BASE_ASSETS = ["release-manifest.json", "SHA256SUMS"]


def latest_release_tag(repo: str) -> str:
    gh = shutil.which("gh")
    if gh:
        proc = subprocess.run([gh, "release", "view", "--repo", repo, "--json", "tagName", "--jq", ".tagName"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag:
        raise SystemExit(f"could not resolve latest release tag for {repo}")
    return tag


def provider_assets() -> list[str]:
    providers = json.loads((Path(__file__).resolve().parent.parent / "providers.json").read_text(encoding="utf-8"))
    targets = providers.get("export_targets", {})
    if not isinstance(targets, dict):
        return []
    return [f"agtmls-{provider}-polyglot.tar.gz" for provider in sorted(targets)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, path: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        path.write_bytes(response.read())


TARBALL_MEMBERS = ["agtmls/index.json", "agtmls/export-manifest.json", "agtmls/ADAPTERS.md"]


def fetch(tag: str, repo: str, out_dir: Path, required_assets: list[str]) -> tuple[int, dict[str, str]]:
    """Download the release into `out_dir`: (gh's exit code or 0, why each
    asset fetched without gh could not be downloaded)."""
    gh = shutil.which("gh")
    if gh:
        proc = subprocess.run([gh, "release", "download", tag, "--repo", repo, "--dir", str(out_dir), "--clobber"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        if proc.returncode != 0:
            print(proc.stdout, end="")
        return proc.returncode, {}
    base = f"https://github.com/{repo}/releases/download/{tag}"
    failed: dict[str, str] = {}
    for name in required_assets:
        try:
            download(f"{base}/{name}", out_dir / name)
        except urllib.error.URLError as exc:
            failed[name] = str(exc)
    return 0, failed


def tarball_problems(name: str, artifact: Path) -> list[str]:
    try:
        with tarfile.open(artifact, "r:gz") as tf:
            names = set(tf.getnames())
    except tarfile.TarError as exc:
        return [f"invalid tarball {name}: {exc}"]
    return [f"{name} missing {required}" for required in TARBALL_MEMBERS if required not in names]


def artifact_problems(out_dir: Path, item: dict, sums: dict[str, str]) -> list[str]:
    """One manifest artifact against SHA256SUMS, the manifest and its contents."""
    name = item["file"]
    artifact = out_dir / name
    if not artifact.exists():
        return [f"manifest artifact missing: {name}"]
    errors = []
    actual = sha256(artifact)
    if sums.get(name) != actual:
        errors.append(f"SHA256SUMS mismatch for {name}")
    if item.get("sha256") != actual:
        errors.append(f"release-manifest checksum mismatch for {name}")
    return errors + tarball_problems(name, artifact)


def stray_sum_problems(out_dir: Path, sums: dict[str, str], in_manifest: set[str]) -> list[str]:
    errors = []
    for name, expected in sums.items():
        # Manifest artifacts were compared against both sources above;
        # this sweep is for summed files the manifest does not list.
        if name == "SHA256SUMS" or name in in_manifest:
            continue
        path = out_dir / name
        if path.exists() and sha256(path) != expected:
            errors.append(f"checksum mismatch for {name}")
    return errors


def manifest_artifacts(path: Path) -> tuple[list[dict], list[str]]:
    """(the manifest's well-formed artifact entries, what is wrong with it)."""
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"release-manifest.json invalid: {exc}"]
    artifacts = manifest.get("artifacts", []) if isinstance(manifest, dict) else None
    if not isinstance(artifacts, list):
        return [], ["release-manifest.json must be an object with an artifacts list"]
    well_formed = [item for item in artifacts if isinstance(item, dict) and isinstance(item.get("file"), str)]
    errors = [f"release-manifest.json artifact {i} must be an object with a file"
              for i, item in enumerate(artifacts) if not (isinstance(item, dict) and isinstance(item.get("file"), str))]
    return well_formed, errors


def asset_problems(out_dir: Path) -> list[str]:
    sums, errors = parse_sums((out_dir / "SHA256SUMS").read_text(encoding="utf-8"))
    artifacts, problems = manifest_artifacts(out_dir / "release-manifest.json")
    errors += problems
    in_manifest = {item["file"] for item in artifacts}
    for item in artifacts:
        errors += artifact_problems(out_dir, item, sums)
    return errors + stray_sum_problems(out_dir, sums, in_manifest)


def report(problems: list[str]) -> int:
    for problem in problems:
        print(f"FAIL: {problem}")
    print()
    print(f"FAIL: {len(problems)} release asset issue(s)")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="latest", help="release tag to verify, or latest")
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    tag = latest_release_tag(args.repo) if args.tag == "latest" else args.tag
    required_assets = [*provider_assets(), *BASE_ASSETS]
    with tempfile.TemporaryDirectory(prefix="agtmls-release-assets-") as td:
        out_dir = args.out_dir or Path(td)
        out_dir.mkdir(parents=True, exist_ok=True)
        code, failed = fetch(tag, args.repo, out_dir, required_assets)
        if code != 0:
            return code
        missing = [name for name in required_assets if not (out_dir / name).exists()]
        if missing:
            return report([f"release asset missing after download: {name}"
                           + (f" ({failed[name]})" if name in failed else "") for name in missing])
        errors = asset_problems(out_dir)
        if errors:
            return report(errors)
        print(f"OK: verified {args.repo} {tag} release assets in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
