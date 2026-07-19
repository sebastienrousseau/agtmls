#!/usr/bin/env python3
"""Health checks for an AgtMLS checkout."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"


def expected_skill_names(bundles: list[str]) -> list[str]:
    names: list[str] = []
    for entry in sorted(SKILLS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if (entry / "SKILL.md").exists():
            names.append(entry.name)
            continue
        if entry.name in bundles:
            for leaf in sorted(entry.iterdir()):
                if (leaf / "SKILL.md").exists():
                    names.append(leaf.name)
    return names


class Reporter:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def ok(self, message: str) -> None:
        print(f"OK   {message}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"WARN {message}")

    def fail(self, message: str) -> None:
        self.failures += 1
        print(f"FAIL {message}")


def run_check(script: str, args: list[str], reporter: Reporter) -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode == 0:
        reporter.ok(f"{script} {' '.join(args)}")
    else:
        reporter.fail(f"{script} {' '.join(args)}")
        print(proc.stdout.rstrip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, help="optional consumer repo to inspect")
    parser.add_argument("--agent", choices=["claude", "codex", "aider"], help="consumer agent layout")
    parser.add_argument("--bundle", action="append", default=[], help="expected project bundle in target")
    parser.add_argument("--skills-only", action="store_true", help="target should not have an AgtMLS prompt")
    args = parser.parse_args()

    r = Reporter()

    for path in ["README.md", "LICENSE", "SECURITY.md", "CONTRIBUTING.md", "CHANGELOG.md", "RELEASE.md", "commands"]:
        p = ROOT / path
        if p.exists():
            r.ok(f"{path} exists")
        else:
            r.fail(f"{path} is missing")

    manifest_path = ROOT / ".claude-plugin" / "plugin.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        r.ok(".claude-plugin/plugin.json exists")
        for key in ["name", "version", "description", "license", "skills"]:
            if manifest.get(key):
                r.ok(f"plugin manifest has {key}")
            else:
                r.fail(f"plugin manifest missing {key}")
        for key in ["skills", "commands"]:
            rel = manifest.get(key)
            if rel and (ROOT / rel).exists():
                r.ok(f"plugin {key} path exists: {rel}")
            elif rel:
                r.fail(f"plugin {key} path missing: {rel}")
    else:
        r.fail(".claude-plugin/plugin.json is missing")

    skill_files = sorted((ROOT / "skills").glob("**/SKILL.md"))
    route_cases = sorted((ROOT / "evals" / "cases").glob("*.json"))
    behavioral_cases = sorted((ROOT / "evals" / "behavioral" / "cases").glob("*.json"))
    if len(route_cases) == len(skill_files):
        r.ok(f"routing eval coverage is complete: {len(route_cases)}/{len(skill_files)}")
    else:
        r.warn(f"routing eval coverage incomplete: {len(route_cases)}/{len(skill_files)}")
    if len(behavioral_cases) == len(skill_files):
        r.ok(f"behavioral eval coverage is complete: {len(behavioral_cases)}/{len(skill_files)}")
    else:
        r.warn(f"behavioral eval coverage incomplete: {len(behavioral_cases)}/{len(skill_files)}")

    checks = json.loads((ROOT / "checks.json").read_text(encoding="utf-8"))["checks"]
    for check in checks:
        parts = shlex.split(check)
        if not parts or parts[0] == "agtmls-doctor.py":
            continue
        run_check(parts[0], parts[1:], r)

    if args.target:
        target = args.target.resolve()
        if not target.exists():
            r.fail(f"target repo does not exist: {target}")
        else:
            r.ok(f"target repo exists: {target}")
            if args.agent:
                dot, prompt = {
                    "claude": (".claude", "CLAUDE.md"),
                    "codex": (".codex", "AGENTS.md"),
                    "aider": (".aider", "CONVENTIONS.md"),
                }[args.agent]
                skills_dir = target / dot / "skills"
                commands_dir = target / dot / "commands"
                if skills_dir.exists():
                    r.ok(f"target {dot}/skills exists")
                else:
                    r.warn(f"target {dot}/skills is missing; run setup-workspace.sh")
                if commands_dir.exists():
                    r.ok(f"target {dot}/commands exists")
                else:
                    r.warn(f"target {dot}/commands is missing; run setup-workspace.sh")
                if skills_dir.exists():
                    missing = []
                    for name in expected_skill_names(args.bundle):
                        link = skills_dir / name
                        if not link.is_symlink() or not str(link.resolve()).startswith(str(ROOT)):
                            missing.append(name)
                    if missing:
                        r.warn(f"target missing expected AgtMLS skill links: {', '.join(missing)}")
                    else:
                        r.ok("target expected AgtMLS skill links are present")
                prompt_path = target / prompt
                if args.skills_only:
                    if prompt_path.exists():
                        first = prompt_path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
                        if first and "Generated by AgtMLS" in first[0]:
                            r.warn(f"target has generated {prompt} despite --skills-only")
                        else:
                            r.ok(f"target {prompt} is hand-authored or absent from AgtMLS")
                    else:
                        r.ok(f"target has no generated {prompt}")
                elif prompt_path.exists():
                    first = prompt_path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
                    if first and "Generated by AgtMLS" in first[0]:
                        r.ok(f"target generated {prompt} exists")
                    else:
                        r.warn(f"target {prompt} exists but is not AgtMLS-generated")
                else:
                    r.warn(f"target generated {prompt} is missing")

    print()
    if r.failures:
        print(f"FAIL: {r.failures} failure(s), {r.warnings} warning(s)")
        return 1
    print(f"OK: doctor passed with {r.warnings} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
