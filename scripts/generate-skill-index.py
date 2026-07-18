#!/usr/bin/env python3
"""Generate index.json for the AgtMLS skill registry.

The index is intentionally derived from files already in the repo. It gives
agents, plugins, and humans a cheap discovery surface without reading every
skill body.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
COMMANDS_DIR = ROOT / "commands"
INDEX = ROOT / "index.json"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"


def load_skill_metadata(skill_dir: Path) -> tuple[str | None, dict[str, object]]:
    direct = skill_dir / "metadata.json"
    if direct.exists():
        return direct.relative_to(ROOT).as_posix(), json.loads(direct.read_text(encoding="utf-8"))
    parts = skill_dir.relative_to(SKILLS_DIR).parts
    if len(parts) > 1:
        bundle_meta = SKILLS_DIR / parts[0] / "metadata.json"
        if bundle_meta.exists():
            return bundle_meta.relative_to(ROOT).as_posix(), json.loads(bundle_meta.read_text(encoding="utf-8"))
    return None, {}


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    key: str | None = None
    buf: list[str] = []
    for line in match.group(1).splitlines():
        top = re.match(r"^([A-Za-z0-9_-]+):[ \t]*(.*)$", line)
        if top and not line.startswith((" ", "\t")):
            if key is not None:
                fields[key] = " ".join(part.strip() for part in buf).strip()
            key = top.group(1)
            value = top.group(2).strip()
            buf = [] if value in {"|", ">", "|-", ">-", "|+", ">+", ""} else [value]
        elif key is not None:
            buf.append(line.strip())
    if key is not None:
        fields[key] = " ".join(part.strip() for part in buf).strip()
    return fields


def collect_commands() -> list[dict[str, object]]:
    commands = []
    for command_md in sorted(COMMANDS_DIR.glob("*.md")) if COMMANDS_DIR.exists() else []:
        if command_md.name == "README.md":
            continue
        text = command_md.read_text(encoding="utf-8")
        fields = parse_frontmatter(text)
        commands.append(
            {
                "name": command_md.stem,
                "description": re.sub(r"\s+", " ", fields.get("description", "")).strip(),
                "path": command_md.relative_to(ROOT).as_posix(),
            }
        )
    return commands


def skill_kind(path: Path) -> tuple[str, str | None]:
    rel = path.parent.relative_to(SKILLS_DIR)
    parts = rel.parts
    if len(parts) == 1:
        return "general", None
    return "project", parts[0]


def infer_tags(name: str, description: str, bundle: str | None) -> list[str]:
    text = f"{name} {description}".lower()
    tags: set[str] = set()
    if bundle:
        tags.add(bundle)
    candidates = {
        "routing": ["routing", "router"],
        "porting": ["porting", "port ", "translate", "cross-language"],
        "noyalib": ["noyalib"],
        "yaml": ["yaml"],
        "ci": ["ci", "workflow"],
        "release": ["release", "tag-driven"],
        "coverage": ["coverage", "llvm-cov"],
        "debugging": ["debugging", "triage"],
        "diagnostics": ["diagnostics", "miri", "criterion", "fuzz"],
        "security": ["security", "unsafe", "secrets"],
        "docs": ["docs", "writing", "rustdoc"],
        "research": ["research", "paper", "frontier"],
        "architecture": ["architecture", "invariant"],
        "config": ["config", "feature", "flags"],
        "validation": ["validation", "evidence"],
        "qa": ["qa", "test"],
    }
    for token, needles in candidates.items():
        if any(needle in text for needle in needles):
            tags.add(token)
    return sorted(tags)


def collect() -> dict[str, object]:
    plugin = json.loads(PLUGIN.read_text(encoding="utf-8")) if PLUGIN.exists() else {}
    commands = collect_commands()
    skills = []
    for skill_md in sorted(SKILLS_DIR.glob("**/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        fields = parse_frontmatter(text)
        kind, bundle = skill_kind(skill_md)
        rel_dir = skill_md.parent.relative_to(ROOT).as_posix()
        references = sorted(
            p.relative_to(skill_md.parent).as_posix()
            for p in skill_md.parent.glob("reference*.md")
        )
        scripts = sorted(
            p.relative_to(skill_md.parent).as_posix()
            for p in skill_md.parent.glob("scripts/*")
            if p.is_file()
        )
        assets = sorted(
            p.relative_to(skill_md.parent).as_posix()
            for p in skill_md.parent.glob("assets/*")
            if p.is_file()
        )
        eval_case = ROOT / "evals" / "cases" / f"{fields.get('name', skill_md.parent.name)}.json"
        behavioral_case = (
            ROOT
            / "evals"
            / "behavioral"
            / "cases"
            / f"{fields.get('name', skill_md.parent.name)}.json"
        )
        metadata_path, metadata = load_skill_metadata(skill_md.parent)
        skills.append(
            {
                "name": fields.get("name", skill_md.parent.name),
                "description": re.sub(r"\s+", " ", fields.get("description", "")).strip(),
                "path": rel_dir,
                "kind": kind,
                "bundle": bundle,
                "license": fields.get("license", "MIT"),
                "date": fields.get("date"),
                "metadata_path": metadata_path,
                "version": metadata.get("version", fields.get("version", "0.1.0")),
                "owner": metadata.get("owner"),
                "maturity": metadata.get("maturity", "hardened" if kind == "general" else "project"),
                "supported_agents": metadata.get("supported_agents", ["claude", "codex", "aider"]),
                "required_tools": metadata.get("required_tools", []),
                "safety_policy": metadata.get("safety_policy", {}),
                "compatibility": fields.get(
                    "compatibility",
                    "agentskills.io-style SKILL.md; tested with Claude Code, Codex, and Aider symlink layouts",
                ),
                "tags": infer_tags(
                    fields.get("name", skill_md.parent.name),
                    fields.get("description", ""),
                    bundle,
                ),
                "references": references,
                "scripts": scripts,
                "assets": assets,
                "evals": {
                    "routing": eval_case.exists(),
                    "behavioral": behavioral_case.exists(),
                },
            }
        )
    bundles = Counter(skill["bundle"] or "_general" for skill in skills)
    routing = sum(1 for skill in skills if skill["evals"]["routing"])
    behavioral = sum(1 for skill in skills if skill["evals"]["behavioral"])
    return {
        "name": "agtmls",
        "description": "Agent Multiple Listing Service skill registry",
        "registry_version": plugin.get("version", "0.0.0"),
        "schema_version": 1,
        "generated_by": "scripts/generate-skill-index.py",
        "skill_count": len(skills),
        "command_count": len(commands),
        "coverage": {
            "routing": {"covered": routing, "total": len(skills)},
            "behavioral": {"covered": behavioral, "total": len(skills)},
        },
        "bundles": dict(sorted(bundles.items())),
        "commands": commands,
        "skills": skills,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write index.json")
    parser.add_argument("--check", action="store_true", help="fail if index.json is stale")
    args = parser.parse_args()

    rendered = json.dumps(collect(), indent=2, sort_keys=True) + "\n"
    if args.write:
        INDEX.write_text(rendered, encoding="utf-8")
        print(f"wrote {INDEX.relative_to(ROOT)}")
        return 0
    if args.check:
        current = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
        if current != rendered:
            print("FAIL: index.json is missing or stale; run python3 scripts/generate-skill-index.py --write")
            return 1
        print("OK: index.json is current")
        return 0
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
