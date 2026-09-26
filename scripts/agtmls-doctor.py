#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
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
PROVIDERS = ROOT / "providers.json"
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import (  # noqa: E402  (needs ROOT on the path first)
    liveness,
    lockfile,
    posture,
)


def native_agents() -> dict[str, tuple[str, str]]:
    """Agent name -> (dot-directory, prompt file), from providers.json.

    A hand-kept copy here rejected `antigravity`, which `agtmls install`
    accepts, so the doctor could not inspect what the installer had made.
    """
    data = json.loads(PROVIDERS.read_text(encoding="utf-8"))
    return {
        name: (str(Path(item["skills_dir"]).parent), item["prompt_file"])
        for name, item in data["native_agents"].items()
    }


def approval_posture(agent: str, target: Path, reporter: Reporter, home: Path | None = None) -> None:
    """Report whether the agent asks before a tool runs, from its own settings.

    A skill's safety_policy is enforced by the user answering the prompt; an
    agent set to run unattended (bypassPermissions, approval_policy = "never",
    yes-always) makes every such policy advisory, which a clean install
    report would otherwise hide.
    """
    item = json.loads(PROVIDERS.read_text(encoding="utf-8"))["native_agents"][agent]
    if not item.get("approval_settings"):
        reporter.ok(f"{agent}: approval settings are not known to AgtMLS; check the agent's own documentation")
        return
    found = posture.settings(item, target, home)
    unattended = [s for s in found if s.unattended]
    for s in unattended:
        reporter.warn(
            f"{agent} runs tools without asking: {s.path} ({s.scope}) sets {s.key} = {s.value}; "
            "every skill's safety_policy is advisory while it does"
        )
    classified = [s for s in found if s.classified]
    for s in classified:
        reporter.ok(
            f"{agent} approves tools by classifier: {s.path} ({s.scope}) sets {s.key} = {s.value}; "
            "calls are judged by a safety classifier rather than asked of you"
        )
    if not unattended and not classified:
        checked = ", ".join(dict.fromkeys(entry["file"] for entry in item["approval_settings"]))
        reporter.ok(f"{agent} asks before tools run: no approval setting switches it off (checked {checked})")


def user_skill_links(reporter: Reporter, home: Path | None = None) -> None:
    """Broken links in each agent's user-level skill directories.

    A lockfile describes one repository's install; a link in ~/.claude/skills
    or ~/.codex/skills is outside every lockfile, and an agent skips a broken
    one without a word. 18 of 20 such links broke when the registry went flat.
    """
    for agent, item in json.loads(PROVIDERS.read_text(encoding="utf-8"))["native_agents"].items():
        links = liveness.user_skill_links(item, home)
        broken = [link for link in links if not link.loadable]
        for link in broken:
            reporter.warn(f"{agent}: {link.directory}/{link.name} is a broken link to {link.target}; the agent skips it")
        if links and not broken:
            reporter.ok(f"{agent}: all {len(links)} linked skill(s) in {', '.join(item['user_skills_dirs'])} resolve")


def expected_skill_names(bundles: list[str]) -> list[str]:
    """The skills an install with these bundles puts in a target.

    The same rule as the installer: a skill whose metadata names a bundle
    lands only when that bundle is asked for. Counting every skill made the
    doctor report eighteen bundled skills missing from a plain install.
    """
    names: list[str] = []
    for entry in sorted(SKILLS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if (entry / "SKILL.md").exists():
            metadata = entry / "metadata.json"
            bundle = (
                json.loads(metadata.read_text(encoding="utf-8")).get("bundle")
                if metadata.exists() else None
            )
            if not bundle or bundle in bundles:
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
    agents = native_agents()
    parser.add_argument("--agent", choices=sorted(agents), help="consumer agent layout")
    parser.add_argument("--bundle", action="append", default=[], help="expected project bundle in target")
    parser.add_argument("--skills-only", action="store_true", help="target should not have an AgtMLS prompt")
    parser.add_argument(
        "--skip-gate",
        action="store_true",
        help="skip re-running checks.json; use inside the gate, which has already run them",
    )
    parser.add_argument(
        "--installed",
        action="store_true",
        help="the registry is an installed package, not a checkout: inspect the registry "
             "and the target, not the repository's documents, evals or gate",
    )
    args = parser.parse_args()

    r = Reporter()

    # The wheel ships the registry, not the repository. Run from it, the
    # previous release's doctor reported 30 failures, every one a governance file, workflow or
    # check the package never contained.
    if args.installed:
        r.ok("installed registry: checkout inspections and the gate are skipped")
    for path in [] if args.installed else [
        "README.md", "SECURITY.md", "CONTRIBUTING.md", "CHANGELOG.md", "RELEASE.md", "commands",
    ]:
        item = ROOT / path
        if item.exists():
            r.ok(f"{path} exists")
        else:
            r.fail(f"{path} is missing")
    if (ROOT / "LICENSE").exists():
        r.ok("LICENSE exists")
    elif (ROOT / "LICENSE-MIT").exists():
        r.ok("LICENSE-MIT exists")
    else:
        r.fail("LICENSE is missing")

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
            value = manifest.get(key)
            # `skills` and `commands` accept a string or an array of paths;
            # bundles need the array form to be discovered at all.
            for rel in value if isinstance(value, list) else [value]:
                if rel and (ROOT / rel).exists():
                    r.ok(f"plugin {key} path exists: {rel}")
                elif rel:
                    r.fail(f"plugin {key} path missing: {rel}")
    else:
        r.fail(".claude-plugin/plugin.json is missing")

    skill_files = sorted((ROOT / "skills").glob("**/SKILL.md"))
    route_cases = sorted((ROOT / "evals" / "cases").glob("*.json"))
    behavioral_cases = sorted((ROOT / "evals" / "behavioral" / "cases").glob("*.json"))
    if args.installed:
        pass  # the evals are the checkout's measure of itself, not the package's
    elif len(route_cases) == len(skill_files):
        r.ok(f"routing eval coverage is complete: {len(route_cases)}/{len(skill_files)}")
    else:
        r.warn(f"routing eval coverage incomplete: {len(route_cases)}/{len(skill_files)}")
    if args.installed:
        pass
    elif len(behavioral_cases) == len(skill_files):
        r.ok(f"behavioral eval coverage is complete: {len(behavioral_cases)}/{len(skill_files)}")
    else:
        r.warn(f"behavioral eval coverage incomplete: {len(behavioral_cases)}/{len(skill_files)}")

    # For a human, `agtmls doctor` running the whole gate is the point. Inside
    # run-all-checks.py it meant every check ran twice -- the duplication was
    # roughly half the gate's wall time.
    checks = [] if args.skip_gate or args.installed else json.loads(
        (ROOT / "checks.json").read_text(encoding="utf-8")
    )["checks"]
    for check in checks:
        parts = shlex.split(check)
        if not parts or parts[0] == "agtmls-doctor.py":
            continue
        run_check(parts[0], parts[1:], r)

    user_skill_links(r)

    if args.target:
        target = args.target.resolve()
        if not target.exists():
            r.fail(f"target repo does not exist: {target}")
        else:
            r.ok(f"target repo exists: {target}")
            if args.agent:
                dot, prompt = agents[args.agent]
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
                    # A wheel install copies; the lockfile says which
                    # directories are ours, so they are not "missing links".
                    lock = lockfile.read(target)
                    copied = (
                        {entry["name"] for entry in lock.get("skills", [])}
                        if lock is not None and lock.get("mode") == "copy" else set()
                    )
                    missing = []
                    for name in expected_skill_names(args.bundle):
                        link = skills_dir / name
                        # is_relative_to, not a string prefix: a sibling
                        # checkout `<root>-experiments` shares the prefix.
                        if link.is_symlink() and link.resolve().is_relative_to(ROOT):
                            continue
                        if name in copied and link.is_dir() and not link.is_symlink():
                            continue
                        missing.append(name)
                    if missing:
                        r.warn(f"target missing expected AgtMLS skill links: {', '.join(missing)}")
                    elif copied:
                        r.ok("target expected AgtMLS skills are present (copied, per the lockfile)")
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
                approval_posture(args.agent, target, r)

    print()
    if r.failures:
        print(f"FAIL: {r.failures} failure(s), {r.warnings} warning(s)")
        return 1
    print(f"OK: doctor passed with {r.warnings} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
