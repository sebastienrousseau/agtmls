#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Every file must declare its licence, in the form its format allows.

REUSE-style headers are the norm, but two file classes cannot carry a leading
comment: `SKILL.md` and `commands/*.md` must begin with `---` at byte 0 or
their frontmatter stops parsing. Those declare `license:` inside the
frontmatter instead — the Agent Skills spec reserves the field for exactly
this. This check enforces whichever form applies, so "add a licence header"
can never silently break a skill.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import licence  # noqa: E402  (scripts path first)

SPDX = "SPDX-License-Identifier"
# Directories that are not ours to header.
SKIP_DIRS = {".git", "dist", "__pycache__", ".ruff_cache", ".agtmls", "node_modules"}
FRONTMATTER_FIRST = {"SKILL.md"}
FRONTMATTER_DIRS = {"commands", "agents"}
# A header is the top of the file: a shebang, then the SPDX lines.
HEADER_LINES = 5
# Workflows, TOML and YAML carry `#` headers like the code does.
PATTERNS = ("*.md", "*.py", "*.sh", "*.yml", "*.yaml", "*.toml")
# Every file carries the expression pyproject.toml declares, spelled the
# same way, so a grep for it finds them all. Read in main(), not at import,
# so a test tree's pyproject is the one that counts.
IDENTIFIER = re.compile(rf"{SPDX}:\s*(.+?)\s*(?:-->)?\s*$", re.MULTILINE)


def frontmatter_licence(text: str) -> str | None:
    """The `license:` value a frontmatter block declares, or None."""
    match = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    found = re.search(r"^license:[ \t]*(\S.*?)[ \t]*$", match.group(1), re.MULTILINE) if match else None
    return found.group(1).strip("'\"") if found else None


def wants_frontmatter(path: Path) -> bool:
    if path.name in FRONTMATTER_FIRST:
        return True
    # README.md inside commands/ documents the directory; it is not a command.
    if path.name == "README.md":
        return False
    rel = path.relative_to(ROOT)
    return len(rel.parts) > 1 and rel.parts[0] in FRONTMATTER_DIRS and path.suffix == ".md"


def declared(text: str, lines: int | None = None) -> str | None:
    """The SPDX expression a file declares, or None when it declares none."""
    head = "\n".join(text.splitlines()[:lines]) if lines else text
    match = IDENTIFIER.search(head)
    return match.group(1) if match else None


def check_identifier(rel: Path, expression: str | None, wanted: str, errors: list[str]) -> None:
    if expression is None:
        errors.append(f"{rel}: missing an {SPDX} header in its first {HEADER_LINES} lines")
    elif expression != wanted:
        errors.append(f"{rel}: declares {expression}, not the project's {wanted}")


def markdown_problems(path: Path, rel: Path, text: str, wanted: str) -> list[str]:
    errors: list[str] = []
    if wants_frontmatter(path):
        # Checked first: a leading comment stops the frontmatter parsing,
        # so behind frontmatter_licence() this could never be reached.
        if text.lstrip().startswith("<!--"):
            errors.append(f"{rel}: frontmatter must start at byte 0; move the licence into `license:`")
        else:
            check_frontmatter(rel, frontmatter_licence(text), wanted, errors)
    elif SPDX not in text:
        errors.append(f"{rel}: missing an {SPDX} header")
    else:
        check_identifier(rel, declared(text, HEADER_LINES), wanted, errors)
    return errors


def check_frontmatter(rel: Path, value: str | None, wanted: str, errors: list[str]) -> None:
    if value is None:
        errors.append(f"{rel}: must declare `license:` in frontmatter")
    elif value != wanted:
        errors.append(f"{rel}: frontmatter declares {value}, not the project's {wanted}")


def file_problems(path: Path, wanted: str) -> list[str]:
    """One file's licence declaration, in the form its format allows."""
    rel = path.relative_to(ROOT)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [f"{rel}: not UTF-8 text"]
    if path.suffix == ".md":
        return markdown_problems(path, rel, text, wanted)
    errors: list[str] = []
    check_identifier(rel, declared(text, HEADER_LINES), wanted, errors)
    return errors


def ours(pattern: str) -> list[Path]:
    """Files matching `pattern`, sorted, outside the directories that are not ours."""
    return [
        path for path in sorted(ROOT.rglob(pattern))
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
    ]


def main() -> int:
    wanted = licence.expression(ROOT)
    if wanted is None:
        print('FAIL: pyproject.toml: no `license = "..."` expression')
        return 1
    errors: list[str] = []
    checked = 0
    for pattern in PATTERNS:
        for path in ours(pattern):
            checked += 1
            errors += file_problems(path, wanted)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} licence header issue(s)")
        return 1
    print(f"OK: licence declared for {checked} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
