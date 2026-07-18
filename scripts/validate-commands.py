#!/usr/bin/env python3
"""Validate command files and plugin command-path consistency."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMANDS = ROOT / "commands"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"


def frontmatter(text: str) -> dict[str, str] | None:
    match = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    if not match:
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        item = re.match(r"^([A-Za-z0-9_-]+):[ \t]*(.+)$", line)
        if item:
            fields[item.group(1)] = item.group(2).strip()
    return fields


def main() -> int:
    errors: list[str] = []
    if not COMMANDS.exists():
        errors.append("commands/ missing")
    if not PLUGIN.exists():
        errors.append(".claude-plugin/plugin.json missing")
    else:
        manifest = json.loads(PLUGIN.read_text(encoding="utf-8"))
        commands_path = manifest.get("commands")
        if commands_path != "./commands":
            errors.append("plugin manifest commands path must be ./commands")
        elif not (ROOT / commands_path).exists():
            errors.append("plugin manifest commands path does not exist")

    command_files = [
        p for p in sorted(COMMANDS.glob("*.md")) if p.name != "README.md"
    ] if COMMANDS.exists() else []
    if not command_files:
        errors.append("commands/ has no command markdown files")
    for cmd in command_files:
        text = cmd.read_text(encoding="utf-8")
        fields = frontmatter(text)
        if fields is None:
            errors.append(f"{cmd.relative_to(ROOT)}: missing YAML frontmatter")
            continue
        if not fields.get("description"):
            errors.append(f"{cmd.relative_to(ROOT)}: missing description")
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$", cmd.name):
            errors.append(f"{cmd.relative_to(ROOT)}: filename must be kebab-case .md")
        if "python3 scripts/agtmls.py" not in text:
            errors.append(f"{cmd.relative_to(ROOT)}: should invoke scripts/agtmls.py")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} command issue(s)")
        return 1
    print(f"OK: {len(command_files)} command file(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
