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
    skill_roots,
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


def _report_setting(agent: str, s, reporter: Reporter) -> None:
    """One setting that changes whether the agent asks before a tool runs."""
    where = f"{s.path} ({s.scope}) sets {s.key} = {s.value}"
    if s.unattended:
        reporter.warn(f"{agent} runs tools without asking: {where}; every skill's safety_policy is advisory while it does")
    elif s.classified:
        reporter.ok(f"{agent} approves tools by classifier: {where}; calls are judged by a safety classifier rather than asked of you")


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
    for s in found:
        _report_setting(agent, s, reporter)
    if not any(s.unattended or s.classified for s in found):
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
    for entry in skill_roots.skill_dirs(ROOT):
        metadata = entry / "metadata.json"
        bundle = (
            json.loads(metadata.read_text(encoding="utf-8")).get("bundle")
            if metadata.exists() else None
        )
        if not bundle or bundle in bundles:
            names.append(entry.name)
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


def parse_args(agents: dict) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, help="optional consumer repo to inspect")
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
    return parser.parse_args()


def check_documents(r: Reporter, installed: bool) -> None:
    # The wheel ships the registry, not the repository. Run from it, the
    # previous release's doctor reported 30 failures, every one a governance file, workflow or
    # check the package never contained.
    if installed:
        r.ok("installed registry: checkout inspections and the gate are skipped")
    for path in [] if installed else [
        "README.md", "SECURITY.md", "CONTRIBUTING.md", "CHANGELOG.md", "RELEASE.md", "commands",
    ]:
        if (ROOT / path).exists():
            r.ok(f"{path} exists")
        else:
            r.fail(f"{path} is missing")
    licence = next((name for name in ("LICENSE", "LICENSE-MIT") if (ROOT / name).exists()), None)
    if licence:
        r.ok(f"{licence} exists")
    else:
        r.fail("LICENSE is missing")


def check_plugin_manifest(r: Reporter) -> None:
    manifest_path = ROOT / ".claude-plugin" / "plugin.json"
    if not manifest_path.exists():
        r.fail(".claude-plugin/plugin.json is missing")
        return
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


def check_eval_coverage(r: Reporter, installed: bool) -> None:
    if installed:
        return  # the evals are the checkout's measure of itself, not the package's
    skills = len(skill_roots.skill_files(ROOT))
    for label, cases in (("routing", ROOT / "evals" / "cases"), ("behavioral", ROOT / "evals" / "behavioral" / "cases")):
        count = len(sorted(cases.glob("*.json")))
        if count == skills:
            r.ok(f"{label} eval coverage is complete: {count}/{skills}")
        else:
            r.warn(f"{label} eval coverage incomplete: {count}/{skills}")


def run_gate(r: Reporter, skip: bool) -> None:
    # For a human, `agtmls doctor` running the whole gate is the point. Inside
    # run-all-checks.py it meant every check ran twice -- the duplication was
    # roughly half the gate's wall time.
    checks = [] if skip else json.loads((ROOT / "checks.json").read_text(encoding="utf-8"))["checks"]
    for check in checks:
        parts = shlex.split(check)
        if parts and parts[0] != "agtmls-doctor.py":
            run_check(parts[0], parts[1:], r)


def check_agent_dirs(r: Reporter, target: Path, dot: str) -> None:
    for sub in ("skills", "commands"):
        if (target / dot / sub).exists():
            r.ok(f"target {dot}/{sub} exists")
        else:
            r.warn(f"target {dot}/{sub} is missing; run setup-workspace.sh")


def installed_here(link: Path, copied: set[str]) -> bool:
    """A link into this registry, or a copy the lockfile records."""
    # is_relative_to, not a string prefix: a sibling
    # checkout `<root>-experiments` shares the prefix.
    if link.is_symlink():
        return link.resolve().is_relative_to(ROOT)
    return link.name in copied and link.is_dir()


def check_skill_links(r: Reporter, target: Path, skills_dir: Path, agent: str, bundles: list[str]) -> None:
    # A wheel install copies; the lockfile says which
    # directories are ours, so they are not "missing links".
    # This agent's entries, whatever `mode` the last install
    # of any agent wrote.
    lock = lockfile.read(target)
    copied = {entry["name"] for entry in lockfile.entries_for(lock, agent)} if lock is not None else set()
    missing = [name for name in expected_skill_names(bundles) if not installed_here(skills_dir / name, copied)]
    if missing:
        r.warn(f"target missing expected AgtMLS skill links: {', '.join(missing)}")
    elif copied:
        r.ok("target expected AgtMLS skills are present (copied, per the lockfile)")
    else:
        r.ok("target expected AgtMLS skill links are present")


def generated(path: Path) -> bool:
    """Whether a prompt file begins with the AgtMLS generated header."""
    first = path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
    return bool(first and "Generated by AgtMLS" in first[0])


def check_prompt(r: Reporter, target: Path, prompt: str, skills_only: bool) -> None:
    prompt_path = target / prompt
    exists = prompt_path.exists()
    if skills_only and not exists:
        r.ok(f"target has no generated {prompt}")
    elif skills_only and generated(prompt_path):
        r.warn(f"target has generated {prompt} despite --skills-only")
    elif skills_only:
        r.ok(f"target {prompt} is hand-authored or absent from AgtMLS")
    elif not exists:
        r.warn(f"target generated {prompt} is missing")
    elif generated(prompt_path):
        r.ok(f"target generated {prompt} exists")
    else:
        r.warn(f"target {prompt} exists but is not AgtMLS-generated")


def check_context(r: Reporter, target: Path, dot: str, prompt: str) -> None:
    """What this install puts in front of the agent in every session: each
    skill's name and description (bodies load only on use) and the prompt
    file. Every skill in the directory counts, whoever installed it."""
    from _lib import context_cost

    skills_dir = target / dot / "skills"
    names = sorted(p.name for p in skills_dir.iterdir() if (p / "SKILL.md").is_file()) if skills_dir.is_dir() else []
    cost = context_cost.install_cost(skills_dir, names, target / prompt)
    skills = f"{cost.skills} skill description(s), about {context_cost.approx_tokens(cost.description_chars):,} tokens"
    if cost.prompt_chars:
        r.ok(f"context: {skills}, and {prompt}, about {context_cost.approx_tokens(cost.prompt_chars):,} tokens,"
             " load in every session")
    else:
        r.ok(f"context: {skills}, load in every session (no {prompt})")


def check_target(r: Reporter, args: argparse.Namespace, agents: dict) -> None:
    target = args.target.resolve()
    if not target.exists():
        r.fail(f"target repo does not exist: {target}")
        return
    r.ok(f"target repo exists: {target}")
    if not args.agent:
        return
    dot, prompt = agents[args.agent]
    check_agent_dirs(r, target, dot)
    if (target / dot / "skills").exists():
        check_skill_links(r, target, target / dot / "skills", args.agent, args.bundle)
    check_prompt(r, target, prompt, args.skills_only)
    check_context(r, target, dot, prompt)
    approval_posture(args.agent, target, r)


def main() -> int:
    agents = native_agents()
    args = parse_args(agents)
    r = Reporter()
    check_documents(r, args.installed)
    check_plugin_manifest(r)
    check_eval_coverage(r, args.installed)
    run_gate(r, args.skip_gate or args.installed)
    user_skill_links(r)
    if args.target:
        check_target(r, args, agents)
    print()
    if r.failures:
        print(f"FAIL: {r.failures} failure(s), {r.warnings} warning(s)")
        return 1
    print(f"OK: doctor passed with {r.warnings} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
