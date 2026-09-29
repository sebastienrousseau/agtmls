#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
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


def manifest_problems() -> list[str]:
    """The plugin manifest points its commands at ./commands, which exists."""
    if not PLUGIN.exists():
        return [".claude-plugin/plugin.json missing"]
    manifest = json.loads(PLUGIN.read_text(encoding="utf-8"))
    commands_path = manifest.get("commands")
    if commands_path != "./commands":
        return ["plugin manifest commands path must be ./commands"]
    if not (ROOT / commands_path).exists():
        return ["plugin manifest commands path does not exist"]
    return []


def command_problems(cmd: Path) -> list[str]:
    text = cmd.read_text(encoding="utf-8")
    fields = frontmatter(text)
    if fields is None:
        return [f"{cmd.relative_to(ROOT)}: missing YAML frontmatter"]
    errors = []
    if not fields.get("description"):
        errors.append(f"{cmd.relative_to(ROOT)}: missing description")
    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$", cmd.name):
        errors.append(f"{cmd.relative_to(ROOT)}: filename must be kebab-case .md")
    if "python3 scripts/agtmls.py" not in text:
        errors.append(f"{cmd.relative_to(ROOT)}: should invoke scripts/agtmls.py")
    return errors


def main() -> int:
    errors: list[str] = [] if COMMANDS.exists() else ["commands/ missing"]
    errors += manifest_problems()

    command_files = [
        p for p in sorted(COMMANDS.glob("*.md")) if p.name != "README.md"
    ] if COMMANDS.exists() else []
    if not command_files:
        errors.append("commands/ has no command markdown files")
    for cmd in command_files:
        errors += command_problems(cmd)

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
