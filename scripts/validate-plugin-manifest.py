#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
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
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import skill_roots  # noqa: E402  (scripts path first)

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


def rel_path(value: object, base: Path | None = None) -> Path | None:
    if not isinstance(value, str) or not value.startswith("./") or ".." in Path(value).parts:
        return None
    return (base or ROOT) / value


def required_skill_paths() -> set[str]:
    """Directories that must appear in a `skills` field. The tree is flat, so
    the skills root covers everything — but a nested skill would be invisible
    to every runtime, so fail loudly if one reappears."""
    nested = sorted(
        "./" + p.parent.relative_to(ROOT).as_posix()
        for p in SKILLS_DIR.glob("*/*/SKILL.md")
    )
    return {"./skills", *nested}


def pack_of_source(source: object) -> str | None:
    """The pack a marketplace entry installs, from its `./packs/<name>` source."""
    if isinstance(source, str):
        parts = Path(source).parts
        if len(parts) == 2 and parts[0] == skill_roots.PACKS:
            return parts[1]
    return None


def check_agent_paths(label: str, value: object, errors: list[str]) -> None:
    """`agents` is an array of file paths. A directory string is rejected by
    `claude plugin validate`, and a stale list silently drops an agent."""
    on_disk = sorted("./" + p.relative_to(ROOT).as_posix() for p in (ROOT / "agents").glob("*.md"))
    if not isinstance(value, list):
        errors.append(f"{label} must be an array of agent file paths, not {type(value).__name__}")
        return
    if sorted(value) != on_disk:
        errors.append(f"{label} does not match agents/ on disk: {sorted(set(on_disk) ^ set(value))}")


def check_skill_paths(label: str, value: object, errors: list[str], base: Path | None = None,
                      required: set[str] | None = None) -> None:
    """`value` resolves against the plugin's source directory `base`; the
    result must cover `required` (repository-relative), by default the
    general skills root."""
    entries = value if isinstance(value, list) else [value]
    resolved: set[str] = set()
    for entry in entries:
        target = rel_path(entry, base)
        if target is None:
            errors.append(f"{label} must contain safe ./ relative paths: {entry!r}")
        elif not target.is_dir():
            errors.append(f"{label} path is not a directory: {entry}")
        else:
            resolved.add("./" + target.relative_to(ROOT).as_posix())
    missing = sorted((required_skill_paths() if required is None else required) - resolved)
    if missing:
        errors.append(
            f"{label} omits bundle path(s) whose skills would not load: {', '.join(missing)}"
        )


def check_plugin_fields(manifest: dict, errors: list[str]) -> None:
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
    check_plugin_owner(manifest, errors)


def check_plugin_owner(manifest: dict, errors: list[str]) -> None:
    author = manifest.get("author")
    if not isinstance(author, dict) or not author.get("name"):
        errors.append("plugin manifest author.name is required")
    homepage = manifest.get("homepage")
    if not isinstance(homepage, str) or not homepage.startswith("https://github.com/"):
        errors.append("plugin manifest homepage must be a GitHub HTTPS URL")


def check_commands_path(value: object, errors: list[str]) -> None:
    commands = rel_path(value)
    if commands is None:
        errors.append("plugin manifest commands must be a safe ./ relative path")
    elif not commands.is_dir():
        errors.append(
            f"plugin manifest commands path must be a directory: {value}"
        )


def check_license_text(license_id: object, errors: list[str]) -> None:
    license_file = ROOT / "LICENSE" if (ROOT / "LICENSE").exists() else ROOT / "LICENSE-MIT"
    license_text = (
        license_file.read_text(encoding="utf-8", errors="replace")
        if license_file.exists()
        else ""
    )
    if license_id in ("MIT", "Apache-2.0 OR MIT") and "MIT License" not in license_text:
        errors.append("LICENSE file must contain MIT License text")


def check_plugin(errors: list[str]) -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    check_plugin_fields(manifest, errors)
    check_skill_paths("plugin manifest skills", manifest.get("skills"), errors)
    check_agent_paths("plugin manifest agents", manifest.get("agents"), errors)
    check_commands_path(manifest.get("commands"), errors)
    check_license_text(manifest.get("license"), errors)
    return manifest


def check_marketplace_identity(catalog: dict, errors: list[str]) -> None:
    name = catalog.get("name")
    if not isinstance(name, str) or not KEBAB.match(name):
        errors.append("marketplace name must be kebab-case")
    elif name in RESERVED_MARKETPLACES:
        errors.append(f"marketplace name {name!r} is reserved for official Anthropic use")

    owner = catalog.get("owner")
    if not isinstance(owner, dict) or not owner.get("name"):
        errors.append("marketplace owner.name is required")


def check_entry_source(label: str, source: object, errors: list[str]) -> None:
    if isinstance(source, str):
        if not source.startswith("./") or ".." in Path(source).parts:
            errors.append(f"{label} source must be a safe ./ relative path or a source object")
    elif not isinstance(source, dict):
        errors.append(f"{label} source is required")


def check_entry_versions(label: str, entry: dict, plugin: dict[str, object], pack: str | None,
                         errors: list[str]) -> None:
    # Version pinning drives updates for installed users; an entry that
    # drifts from plugin.json ships stale metadata to the catalog.
    if entry.get("name") == plugin.get("name"):
        for field in ("version", "license", "homepage"):
            if entry.get(field) != plugin.get(field):
                errors.append(
                    f"{label} {field} ({entry.get(field)!r}) "
                    f"!= plugin.json ({plugin.get(field)!r})"
                )
    elif pack is not None and entry.get("version") != plugin.get("version"):
        errors.append(f"{label} version ({entry.get('version')!r}) != plugin.json ({plugin.get('version')!r})")


def check_marketplace_entry(entry: dict, plugin: dict[str, object], errors: list[str]) -> str | None:
    """Check one plugin entry; return the pack it serves, if any."""
    label = f"marketplace plugin {entry.get('name', '<unnamed>')!r}"
    if not isinstance(entry.get("name"), str) or not KEBAB.match(entry.get("name", "")):
        errors.append(f"{label} name must be kebab-case")
    source = entry.get("source")
    check_entry_source(label, source, errors)
    pack = pack_of_source(source)
    if "skills" in entry:
        check_skill_paths(
            f"{label} skills", entry["skills"], errors,
            base=ROOT / source if isinstance(source, str) else None,
            required={f"./{skill_roots.PACKS}/{pack}/skills"} if pack else None,
        )
    if "agents" in entry:
        check_agent_paths(f"{label} agents", entry["agents"], errors)
    check_entry_versions(label, entry, plugin, pack, errors)
    return pack


def check_marketplace(plugin: dict[str, object], errors: list[str]) -> None:
    catalog = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    check_marketplace_identity(catalog, errors)

    entries = catalog.get("plugins")
    if not isinstance(entries, list) or not entries:
        errors.append("marketplace plugins must be a non-empty array")
        return

    listed = {entry.get("name") for entry in entries if isinstance(entry, dict)}
    if plugin.get("name") not in listed:
        errors.append(f"marketplace does not list the plugin {plugin.get('name')!r}")

    packed: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("marketplace plugin entry must be an object")
            continue
        pack = check_marketplace_entry(entry, plugin, errors)
        if pack is not None:
            packed.add(pack)
    # A pack is left out of the default plugin, so the marketplace is the only
    # way its skills load as a plugin at all.
    for pack in sorted(set(skill_roots.packs(ROOT)) - packed):
        errors.append(f"marketplace lists no plugin for pack {pack!r} (source ./{skill_roots.PACKS}/{pack})")


def main() -> int:
    errors: list[str] = []
    for path, label in ((MANIFEST, "plugin.json"), (MARKETPLACE, "marketplace.json")):
        if not path.exists():
            print(f"FAIL: .claude-plugin/{label} missing; run generate-plugin-manifests.py --write")
            return 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"FAIL: .claude-plugin/{label} invalid JSON: {exc}; fix it by hand or "
                  "regenerate with generate-plugin-manifests.py --write")
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
