# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Auditing a foreign tree: a repository of skills that is not this one.

`audit --foreign` finds every skill a tree ships, whatever its layout,
audits each distinct one against its own or a provisional policy, and
states what it did not read. The per-file detectors live in analyzer.py;
this module decides what to feed them.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import NamedTuple

from .analyzer import (
    AUDITABLE_SUFFIXES,
    SKIP_PARTS,
    audit_file,
    auditable_files,
)
from .digest import skill_digest
from .findings import Finding, read_capped
from .policy import (
    check_capability_escalation,
    check_skill_honesty,
    frontmatter_tools,
    load_policy,
)
from .rules import TOOL_CAPABILITIES


class ForeignLayoutError(ValueError):
    """The tree is not something the foreign audit can read as skills."""


# Manifests whose `skills` field names the skill directories, in the order a
# repository is most likely to be one thing rather than another.
PLUGIN_MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".cursor-plugin/plugin.json")
SKILL_LAYOUTS = (".agents/skills", ".claude/skills", "skills")


def _inside(root: Path, rel: str) -> Path | None:
    """`rel` joined under `root`, or None if it escapes.

    The escape check resolves; the returned path does not, so callers can
    relate it to the root they gave (macOS resolves /var to /private/var).
    """
    candidate = root / rel
    return candidate if candidate.resolve().is_relative_to(root.resolve()) else None


def _skills_under(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p.parent for p in directory.glob("*/SKILL.md"))


def _manifest_skills(root: Path, manifest: Path, default_name: str) -> list[tuple[str, Path]]:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    name = str(data.get("name") or default_name)
    declared = data.get("skills") or ["./skills"]
    found: list[tuple[str, Path]] = []
    for rel in declared if isinstance(declared, list) else [declared]:
        directory = _inside(root, str(rel)) if isinstance(rel, str) else None
        if directory is not None:
            found.extend((name, skill) for skill in _skills_under(directory))
    return found


def foreign_layout(root: Path) -> str | None:
    """Which layout a tree follows, or None."""
    if (root / ".claude-plugin" / "marketplace.json").is_file():
        return "claude-marketplace"
    for manifest in PLUGIN_MANIFESTS:
        if (root / manifest).is_file():
            return manifest.split("/")[0].strip(".").replace("-plugin", "-plugin")
    for layout in SKILL_LAYOUTS:
        if _skills_under(root / layout):
            return layout
    return None


def _marketplace_plugins(marketplace: Path) -> list:
    """The `plugins` a marketplace lists, or [] when it cannot be read."""
    try:
        catalog = json.loads(marketplace.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    plugins = catalog.get("plugins", []) if isinstance(catalog, dict) else []
    return plugins if isinstance(plugins, list) else []


def _plugin_skills(root: Path, entry: object) -> list[tuple[str, Path]]:
    """Skills of one marketplace entry: its plugin manifest's, or its skills directory's."""
    if not isinstance(entry, dict) or not isinstance(entry.get("source"), str):
        return []
    plugin_dir = _inside(root, entry["source"])
    if plugin_dir is None:
        return []
    name = str(entry.get("name") or plugin_dir.name)
    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    if manifest.is_file():
        return _manifest_skills(plugin_dir, manifest, name)
    return [(name, skill) for skill in _skills_under(plugin_dir / "skills")]


def _declared_skills(root: Path) -> list[tuple[str, Path]]:
    """Skills the tree's own manifests and conventional directories declare."""
    found: list[tuple[str, Path]] = []
    marketplace = root / ".claude-plugin" / "marketplace.json"
    if marketplace.is_file():
        for entry in _marketplace_plugins(marketplace):
            found.extend(_plugin_skills(root, entry))
    for manifest in PLUGIN_MANIFESTS:
        if (root / manifest).is_file():
            found.extend(_manifest_skills(root, root / manifest, root.name))
    for layout in SKILL_LAYOUTS:
        found.extend((layout, skill) for skill in _skills_under(root / layout))
    return found


def _walk(root: Path):
    """(directory, subdirectories, files) under `root`, never following a
    symlink and never entering a dependency, cache or VCS directory."""
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_PARTS)
        yield Path(current), dirs, sorted(files)


def _discovered_skills(root: Path) -> list[Path]:
    """Every directory under `root` holding a SKILL.md, the root excepted.

    A skill's own subdirectories are part of it and are not searched again,
    so a nested example SKILL.md is audited once, with its skill.
    """
    found: list[Path] = []
    for current, dirs, files in _walk(root):
        if current != root and "SKILL.md" in files:
            found.append(current)
            dirs[:] = []
    return found


def foreign_skills(root: Path) -> list[tuple[str, Path]]:
    """(source, skill directory) for every skill a foreign tree ships.

    First every layout the tree declares: a Claude marketplace (each listed
    plugin's skills), plugin manifests (their `skills` paths) and the
    conventional directories (`.agents/skills`, `.claude/skills`,
    `skills`). Then a sweep of the whole tree finds every other SKILL.md, as
    per-harness copies (`.cursor/skills`, `.gemini/skills`, ...) and
    embedded asset trees that no manifest names; those are labelled by the
    directory that holds them. Stopping at the first layout audited 1 of 24
    skills in one real repository and reported the rest as clean.

    A SKILL.md at the root with nothing else is refused: one repository read
    as one skill audits everything in it as prose and calls a whole project
    a skill, which is what ruflo's root SKILL.md did.
    """
    found: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for source, skill in _declared_skills(root):
        key = skill.resolve()
        if key not in seen:
            seen.add(key)
            found.append((source, skill))
    for skill in _discovered_skills(root):
        key = skill.resolve()
        if key not in seen:
            seen.add(key)
            found.append((skill.parent.relative_to(root).as_posix(), skill))
    if not found:
        if (root / "SKILL.md").is_file():
            raise ForeignLayoutError(
                f"a repository is not a skill: {root} has SKILL.md at its root and no skills directory; "
                "point at the skill directory itself to audit one skill"
            )
        raise ForeignLayoutError(f"no skills found under {root}: expected a marketplace, a plugin manifest, or a skills directory")
    return found


def provisional_policy(skill_dir: Path) -> dict:
    """A safety policy inferred from allowed-tools, for a skill that declares none.

    Any Bash grants executes_commands; Write or Edit grants writes_files;
    WebFetch or WebSearch makes network optional. Marked provisional, so a
    report never presents it as the author's own claim.
    """
    capabilities = {TOOL_CAPABILITIES.get(tool.split("(", 1)[0]) for tool in frontmatter_tools(skill_dir / "SKILL.md")}
    return {
        "executes_commands": "executes_commands" in capabilities,
        "writes_files": "writes_files" in capabilities,
        "network_access": "optional" if "network_access" in capabilities else "none",
        "handles_secrets": False,
        "provisional": True,
    }


class ForeignReport(NamedTuple):
    plugin: str
    path: Path
    policy: dict
    findings: list[Finding]
    digest: str | None = None
    copies: tuple[Path, ...] = ()


def _skill_digest(skill_dir: Path) -> str | None:
    try:
        return skill_digest(skill_dir)
    except OSError:
        return None


def audit_foreign(root: Path, pedantic: bool = False) -> list[ForeignReport]:
    """Every distinct skill in a foreign tree, each against its own or a
    provisional policy.

    Byte-identical copies (one skill shipped once per harness) share a
    digest and are audited once; the report names every copy. A copy whose
    bytes differ is a different skill and is audited on its own.
    """
    groups: dict[object, list[tuple[str, Path]]] = {}
    for plugin, skill_dir in foreign_skills(root):
        digest = _skill_digest(skill_dir)
        groups.setdefault(digest if digest is not None else skill_dir, []).append((plugin, skill_dir))
    reports: list[ForeignReport] = []
    for key, members in groups.items():
        plugin, skill_dir = members[0]
        findings: list[Finding] = []
        for path in auditable_files(skill_dir):
            findings.extend(audit_file(path, pedantic))
        if (skill_dir / "metadata.json").exists():
            policy, policy_findings = load_policy(skill_dir)
            findings.extend(policy_findings)
            findings.extend(check_skill_honesty(skill_dir))
        else:
            policy = provisional_policy(skill_dir)
            findings.extend(check_capability_escalation(skill_dir, policy))
        reports.append(ForeignReport(plugin, skill_dir, policy, findings,
                                     key if isinstance(key, str) else None,
                                     tuple(path for _, path in members[1:])))
    return reports


# Files that change what an agent does without being a skill: hook wiring,
# harness settings, plugin and MCP manifests. The coverage statement names
# any it did not audit, so a clean result is never read as covering them.
AGENT_CONFIG_NAMES = {
    "hooks.json", "settings.json", "settings.local.json", "plugin.json", "marketplace.json",
    ".mcp.json", "mcp.json", "config.toml", "AGENTS.md", "CLAUDE.md", "GEMINI.md",
}


def _skill_name(skill_dir: Path) -> str:
    text = read_capped(skill_dir / "SKILL.md") or ""
    match = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    field = re.search(r"^name:[ \t]*[\"']?([^\"'\n]+?)[\"']?[ \t]*$", match.group(1), re.MULTILINE) if match else None
    return field.group(1).strip() if field else skill_dir.name


def _is_auditable(path: Path) -> bool:
    """A regular file with an auditable suffix or an executable bit."""
    try:
        mode = path.lstat().st_mode
    except OSError:
        return False
    return stat.S_ISREG(mode) and bool(path.suffix.lower() in AUDITABLE_SUFFIXES or mode & 0o111)


def _count_skipped(current: Path, skipped: dict[str, int]) -> None:
    with os.scandir(current) as entries:
        for entry in entries:
            if entry.is_dir(follow_symlinks=False) and entry.name in SKIP_PARTS:
                skipped[entry.name] = skipped.get(entry.name, 0) + 1


def _outside_skills(root: Path, inside: set[Path]) -> tuple[list[str], dict[str, int]]:
    """(auditable files outside every skill, skipped directories by name)."""
    outside: list[str] = []
    skipped: dict[str, int] = {}
    for current, dirs, files in _walk(root):
        resolved = current.resolve()
        if resolved in inside or any(parent in inside for parent in resolved.parents):
            dirs[:] = []
            continue
        _count_skipped(current, skipped)
        outside += [(current / name).relative_to(root).as_posix() for name in files if _is_auditable(current / name)]
    return outside, skipped


def _area(rel: str) -> str:
    """The top two directories of a path, the top one, or "." at the root."""
    parts = rel.split("/")
    if len(parts) > 2:
        return "/".join(parts[:2]) + "/"
    return parts[0] + "/" if len(parts) > 1 else "."


def _by_area(outside: list[str]) -> dict[str, int]:
    """Unaudited files counted by area, the largest first."""
    by_area: dict[str, int] = {}
    for rel in outside:
        by_area[_area(rel)] = by_area.get(_area(rel), 0) + 1
    return dict(sorted(by_area.items(), key=lambda kv: (-kv[1], kv[0])))


def _divergent_copies(root: Path, reports: list[ForeignReport]) -> dict[str, list[str]]:
    """Skill names shipped with more than one distinct digest, and where."""
    names: dict[str, set[str | None]] = {}
    where: dict[str, list[str]] = {}
    for r in reports:
        for path in (r.path, *r.copies):
            name = _skill_name(path)
            names.setdefault(name, set()).add(r.digest)
            where.setdefault(name, []).append(path.relative_to(root).as_posix())
    return {name: sorted(where[name]) for name, digests in sorted(names.items()) if len(digests) > 1}


def source_commit(root: Path) -> str | None:
    """The commit of the git checkout whose top is `root`, or None.

    Pinning is the first step of vetting, and an agent otherwise spends
    turns probing for it. A directory inside some other checkout is not
    pinned by that checkout's commit, so only the top of one counts.
    """
    argv = ["git", "-C", str(root), "rev-parse", "--show-toplevel", "HEAD"]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = proc.stdout.split()
    if proc.returncode != 0 or len(lines) != 2 or Path(lines[0]).resolve() != root.resolve():
        return None
    return lines[1]


def foreign_coverage(root: Path, reports: list[ForeignReport]) -> dict:
    """What a foreign audit read, what it did not, and why.

    An unscanned file is not a clean one: the statement counts the skills
    found and audited, the files audited, every auditable file outside any
    skill (with agent configs such as hooks.json named), the dependency and
    cache directories skipped, and skills whose copies disagree.
    """
    skill_dirs = [r.path for r in reports] + [c for r in reports for c in r.copies]
    inside = {d.resolve() for d in skill_dirs}
    audited = {p for r in reports for p in auditable_files(r.path)}
    outside, skipped = _outside_skills(root, inside)
    return {
        "skills_found": len(skill_dirs),
        "skills_audited": len(reports),
        "duplicate_copies": sum(len(r.copies) for r in reports),
        "files_audited": len(audited),
        "files_not_audited": len(outside),
        "not_audited_files": sorted(outside),
        "not_audited_by_area": _by_area(outside),
        "agent_configs_not_audited": sorted(rel for rel in outside if rel.rsplit("/", 1)[-1] in AGENT_CONFIG_NAMES),
        "skipped_directories": dict(sorted(skipped.items())),
        "divergent_copies": _divergent_copies(root, reports),
        "source_commit": source_commit(root),
    }
