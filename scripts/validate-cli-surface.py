#!/usr/bin/env python3
"""Validate CLI subcommands against docs and command files."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"
README = ROOT / "README.md"
COMMAND = ROOT / "commands" / "agtmls.md"


def subcommands() -> set[str]:
    tree = ast.parse(CLI.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_parser":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            found.add(node.args[0].value)
    return found


def main() -> int:
    errors: list[str] = []
    expected = {
        "doctor",
        "status",
        "check",
        "list",
        "search",
        "show",
        "stats",
        "profiles",
        "providers",
        "export",
        "diff",
        "release-check",
        "import-skill",
        "index",
        "install",
        "uninstall",
        "propose-skill",
        "scaffold-skill",
    }
    found = subcommands()
    if found != expected:
        errors.append(f"CLI subcommands mismatch: expected {sorted(expected)}, found {sorted(found)}")
    readme = README.read_text(encoding="utf-8")
    command = COMMAND.read_text(encoding="utf-8")
    for name in expected:
        if f"agtmls.py {name}" not in readme and name not in {"doctor"}:
            errors.append(f"README missing agtmls.py {name} example or mention")
    if "agtmls.py status" not in command:
        errors.append("commands/agtmls.md must invoke agtmls.py status")
    if re.search(r"agtmls.py\s+list\s+commands", readme) is None:
        errors.append("README missing agtmls.py list commands example")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} CLI surface issue(s)")
        return 1
    print(f"OK: CLI surface valid with {len(found)} subcommand(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
