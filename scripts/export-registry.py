#!/usr/bin/env python3
"""Export a provider-neutral AgtMLS bundle."""

from __future__ import annotations

import argparse
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_json(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def selected_skill_paths(profile_name: str | None, bundle: list[str]) -> list[Path]:
    index = load_json("index.json")
    profiles = load_json("profiles.json").get("profiles", {})
    wanted_skills: set[str] | None = None
    wanted_bundles = set(bundle)
    if profile_name:
        profile = profiles.get(profile_name)
        if not isinstance(profile, dict):
            raise SystemExit(f"unknown profile: {profile_name}")
        wanted_skills = set(profile.get("skills", []))
        wanted_bundles.update(profile.get("bundles", []))
    paths = []
    for skill in index.get("skills", []):
        include = wanted_skills is None and not wanted_bundles
        include = include or skill.get("name") in (wanted_skills or set())
        include = include or skill.get("bundle") in wanted_bundles
        if include:
            paths.append(ROOT / str(skill["path"]))
    return sorted(set(paths))


def copytree(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc")
    shutil.copytree(src, dst, ignore=ignore)


def build(out_dir: Path, provider: str, profile: str | None, bundle: list[str]) -> Path:
    providers = load_json("providers.json")
    targets = providers.get("export_targets", {})
    if provider not in targets:
        raise SystemExit(f"unknown provider export target: {provider}")
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"agtmls-{provider}{('-' + profile) if profile else ''}.tar.gz"
    with tempfile.TemporaryDirectory(prefix="agtmls-export-") as td:
        staging = Path(td) / "agtmls"
        (staging / "skills").mkdir(parents=True)
        for skill_path in selected_skill_paths(profile, bundle):
            copytree(skill_path, staging / "skills" / skill_path.name)
        for rel in ["commands", "system-prompts"]:
            if (ROOT / rel).exists():
                copytree(ROOT / rel, staging / rel)
        for rel in ["index.json", "profiles.json", "providers.json", "CATALOG.md", "README.md", "LICENSE"]:
            if (ROOT / rel).exists():
                shutil.copy2(ROOT / rel, staging / rel)
        manifest = {
            "schema_version": 1,
            "provider": provider,
            "profile": profile,
            "bundles": bundle,
            "skill_count": len(list((staging / "skills").iterdir())),
            "format": "provider-neutral-markdown",
        }
        (staging / "export-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(staging, arcname="agtmls")
    print(archive)
    return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="generic")
    parser.add_argument("--profile")
    parser.add_argument("--bundle", action="append", default=[])
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    build(args.out_dir, args.provider, args.profile, args.bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
