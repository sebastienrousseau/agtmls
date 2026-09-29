#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate CLI subcommands against docs and command files."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The subcommands moved out of agtmls.py so the surface could be read on
# its own. This check follows them rather than parsing the dispatch.
CLI = ROOT / "scripts" / "_lib" / "cli_parser.py"
README = ROOT / "README.md"
# The command reference moved out of the README to keep it readable; the
# surface must still be documented somewhere a user will find it.
CLI_DOC = ROOT / "docs" / "cli.md"
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


EXPECTED = {
    "doctor",
    "status",
    "check",
    "audit",
    "list",
    "search",
    "show",
    "stats",
    "profiles",
    "providers",
    "export",
    "docs-site",
    "release-pack",
    "verify-release-assets",
    "release-dry-run",
    "next-version",
    "bump-version",
    "evolve",
    "evidence",
    "mcp-resources",
    "plugin-manifests",
    "sbom",
    "provenance",
    "provider-install",
    "bench",
    "diff",
    "release-check",
    "import-skill",
    "index",
    "install",
    "uninstall",
    "verify",
    "propose-skill",
    "scaffold-skill",
}


def doc_problems(readme: str, command: str) -> list[str]:
    """Every subcommand is shown in the README or docs/cli.md, and the command file invokes status."""
    errors = [
        f"README/docs/cli.md missing agtmls.py {name} example or mention"
        for name in EXPECTED
        if f"agtmls.py {name}" not in readme and name not in {"doctor"}
    ]
    if "agtmls.py status" not in command:
        errors.append("commands/agtmls.md must invoke agtmls.py status")
    if re.search(r"agtmls.py\s+list\s+commands", readme) is None:
        errors.append("README missing agtmls.py list commands example")
    return errors


def main() -> int:
    errors: list[str] = []
    found = subcommands()
    if found != EXPECTED:
        errors.append(f"CLI subcommands mismatch: expected {sorted(EXPECTED)}, found {sorted(found)}")
    readme = README.read_text(encoding="utf-8")
    if CLI_DOC.exists():
        readme += CLI_DOC.read_text(encoding="utf-8")
    else:
        errors.append("docs/cli.md is missing; the CLI surface must stay documented")
    errors += doc_problems(readme, COMMAND.read_text(encoding="utf-8"))
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
