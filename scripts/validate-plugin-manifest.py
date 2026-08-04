#!/usr/bin/env python3
"""Validate the AgtMLS plugin manifest and marketplace catalog.

Two manifests gate distribution through the Claude Code plugin system:

  .claude-plugin/plugin.json       what the plugin contains
  .claude-plugin/marketplace.json  how users discover and install it

Both are checked here. The load-bearing rule is `skills` coverage: the
plugin `skills` field is a non-recursive scan of directories holding
`<name>/SKILL.md`. The skill tree is deliberately flat so a single
`./skills` path covers all of it, and this validator re-derives the
required path set from the tree — if a nested skill ever reappears it
would be invisible to every runtime, and the check fails.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
SKILLS_DIR = ROOT / "skills"
REQUIRED = ["name", "version", "description", "author", "license", "homepage", "skills", "commands"]
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Marketplace names Anthropic reserves for official use; a third-party
# catalog registered under one of these stops loading entirely.
RESERVED_MARKETPLACES = {
    "agent-skills",
    "anthropic-agent-skills",
    "anthropic-marketplace",
    "anthropic-plugins",
    "claude-code-marketplace",
    "claude-code-plugins",
    "claude-community",
    "claude-for-financial-services",
    "claude-for-legal",
    "claude-plugins-community",
    "claude-plugins-official",
    "financial-services-plugins",
    "first-party-plugins",
    "healthcare",
    "knowledge-work-plugins",
    "life-sciences",
}


def rel_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.startswith("./") or ".." in Path(value).parts:
        return None
    return ROOT / value


def required_skill_paths() -> set[str]:
    """Directories that must appear in a `skills` field. The tree is flat, so
    the skills root covers everything — but a nested skill would be invisible
    to every runtime, so fail loudly if one reappears."""
    nested = sorted(
        "./" + p.parent.relative_to(ROOT).as_posix()
        for p in SKILLS_DIR.glob("*/*/SKILL.md")
    )
    return {"./skills", *nested}


def check_skill_paths(label: str, value: object, errors: list[str]) -> None:
    entries = value if isinstance(value, list) else [value]
    resolved: set[str] = set()
    for entry in entries:
        target = rel_path(entry)
        if target is None:
            errors.append(f"{label} must contain safe ./ relative paths: {entry!r}")
        elif not target.is_dir():
            errors.append(f"{label} path is not a directory: {entry}")
        else:
            resolved.add("./" + target.relative_to(ROOT).as_posix())
    missing = sorted(required_skill_paths() - resolved)
    if missing:
        errors.append(
            f"{label} omits bundle path(s) whose skills would not load: {', '.join(missing)}"
        )


def check_plugin(errors: list[str]) -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    for field in REQUIRED:
        if field not in manifest:
            errors.append(f"plugin manifest missing {field}")
    if manifest.get("name") != "agtmls":
        errors.append("plugin manifest name must be agtmls")
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.match(version):
        errors.append("plugin manifest version must be semver")
    if manifest.get("license") != "MIT":
        errors.append("plugin manifest license must be MIT")
    author = manifest.get("author")
    if not isinstance(author, dict) or not author.get("name"):
        errors.append("plugin manifest author.name is required")
    homepage = manifest.get("homepage")
    if not isinstance(homepage, str) or not homepage.startswith("https://github.com/"):
        errors.append("plugin manifest homepage must be a GitHub HTTPS URL")

    check_skill_paths("plugin manifest skills", manifest.get("skills"), errors)

    commands = rel_path(manifest.get("commands"))
    if commands is None:
        errors.append("plugin manifest commands must be a safe ./ relative path")
    elif not commands.is_dir():
        errors.append(
            f"plugin manifest commands path must be a directory: {manifest.get('commands')}"
        )

    license_text = (
        (ROOT / "LICENSE").read_text(encoding="utf-8", errors="replace")
        if (ROOT / "LICENSE").exists()
        else ""
    )
    if manifest.get("license") == "MIT" and "MIT License" not in license_text:
        errors.append("LICENSE file must contain MIT License text")
    return manifest


def check_marketplace(plugin: dict[str, object], errors: list[str]) -> None:
    catalog = json.loads(MARKETPLACE.read_text(encoding="utf-8"))

    name = catalog.get("name")
    if not isinstance(name, str) or not KEBAB.match(name):
        errors.append("marketplace name must be kebab-case")
    elif name in RESERVED_MARKETPLACES:
        errors.append(f"marketplace name {name!r} is reserved for official Anthropic use")

    owner = catalog.get("owner")
    if not isinstance(owner, dict) or not owner.get("name"):
        errors.append("marketplace owner.name is required")

    entries = catalog.get("plugins")
    if not isinstance(entries, list) or not entries:
        errors.append("marketplace plugins must be a non-empty array")
        return

    listed = {entry.get("name") for entry in entries if isinstance(entry, dict)}
    if plugin.get("name") not in listed:
        errors.append(f"marketplace does not list the plugin {plugin.get('name')!r}")

    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("marketplace plugin entry must be an object")
            continue
        label = f"marketplace plugin {entry.get('name', '<unnamed>')!r}"
        if not isinstance(entry.get("name"), str) or not KEBAB.match(entry.get("name", "")):
            errors.append(f"{label} name must be kebab-case")
        source = entry.get("source")
        if isinstance(source, str):
            if not source.startswith("./") or ".." in Path(source).parts:
                errors.append(f"{label} source must be a safe ./ relative path or a source object")
        elif not isinstance(source, dict):
            errors.append(f"{label} source is required")
        if "skills" in entry:
            check_skill_paths(f"{label} skills", entry["skills"], errors)
        # Version pinning drives updates for installed users; an entry that
        # drifts from plugin.json ships stale metadata to the catalog.
        if entry.get("name") == plugin.get("name"):
            for field in ("version", "license", "homepage"):
                if entry.get(field) != plugin.get(field):
                    errors.append(
                        f"{label} {field} ({entry.get(field)!r}) "
                        f"!= plugin.json ({plugin.get(field)!r})"
                    )


def main() -> int:
    errors: list[str] = []
    for path, label in ((MANIFEST, "plugin.json"), (MARKETPLACE, "marketplace.json")):
        if not path.exists():
            print(f"FAIL: .claude-plugin/{label} missing")
            return 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"FAIL: .claude-plugin/{label} invalid JSON: {exc}")
            return 1

    plugin = check_plugin(errors)
    check_marketplace(plugin, errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} manifest issue(s)")
        return 1
    print("OK: plugin manifest and marketplace catalog valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
