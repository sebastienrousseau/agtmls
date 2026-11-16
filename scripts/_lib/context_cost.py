# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What an install puts in front of an agent in every session.

Skill bodies load only when a skill is used, but every installed skill's
name and description, and the prompt file (CLAUDE.md, AGENTS.md), are read
in every session. `doctor` reports that cost for an install.

There is no ceiling here to feed. Each agent has its own listing budget and
shortens descriptions past it, and the documented figure (Codex: 2% of the
context or 8,000 characters) did not bind in practice: all 33 skills, a
13,034-character listing, reached Codex in full on 29 September 2026. So
`verify --live` compares what the agent actually shows with each skill's own
description, and names any it shortened.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

from . import frontmatter

# A rough English average. Every figure built on it is labelled "about".
CHARS_PER_TOKEN = 4
DESCRIPTION = re.compile(r"^description:[ \t]*(.*)$", re.MULTILINE)
# A block scalar header: `|` or `>`, then a chomping (`+`/`-`) and an
# indentation (1-9) indicator in either order, then an optional comment.
BLOCK_HEADER = re.compile(r"^([|>])(?:([+-])([1-9])?|([1-9])([+-])?)?[ \t]*(?:#.*)?$")


class Cost(NamedTuple):
    skills: int
    description_chars: int
    prompt_chars: int


def approx_tokens(chars: int) -> int:
    return -(-chars // CHARS_PER_TOKEN)


def _unquote(value: str) -> str:
    if len(value) < 2 or value[0] != value[-1] or value[0] not in "\"'":
        return value
    if value[0] == "'":
        return value[1:-1]
    try:
        return json.loads(value)  # a double-quoted YAML scalar escapes as JSON does
    except ValueError:
        return value[1:-1]


def description(skill_md: Path) -> str:
    """The frontmatter description as an agent reads it: unquoted, or "" when
    there is none to read."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return ""
    parts = frontmatter.split(text)
    field = DESCRIPTION.search(parts[0]) if parts else None
    if not field:
        return ""
    value = field.group(1).strip()
    header = BLOCK_HEADER.match(value)
    if header:
        return _block_scalar(header, parts[0][field.end():].split("\n")[1:])
    return _unquote(value)


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _ends_block(line: str, indent: int) -> bool:
    """A content line indented less than the block ends it."""
    return bool(line.strip()) and (indent == 0 or _indent_of(line) < indent)


def _block_body(lines: list[str], indent: int | None) -> list[str]:
    """The block's lines with its indentation removed: `indent` when the header
    gave one, else the first content line's. A whitespace-only line keeps the
    spaces past that indentation; the block ends at a less-indented line."""
    if indent is None:
        indent = next((_indent_of(line) for line in lines if line.strip()), 0)
    body: list[str] = []
    for line in lines:
        if _ends_block(line, indent):
            break
        body.append(line[indent:])
    return body


def _separator(previous: str | None, kind: str, empties: int) -> str:
    """What joins a folded line to the one before it: a space between two
    ordinary lines, a newline per empty line, and a kept break next to a
    more-indented line."""
    if previous is None:
        return "\n" * empties
    if previous == kind == "normal":
        return "\n" * empties or " "
    return "\n" * (empties + 1)


def _fold(lines: list[str]) -> str:
    """YAML folding of a block's content lines."""
    text, empties, previous = "", 0, None
    for line in lines:
        if not line:
            empties += 1
            continue
        kind = "more" if line[0] in " \t" else "normal"
        text += _separator(previous, kind, empties) + line
        empties, previous = 0, kind
    return text


def _header(match: re.Match) -> tuple[str, str, int | None]:
    """(style, chomping indicator, explicit indentation) of a block header."""
    explicit = match.group(3) or match.group(4)
    return match.group(1), match.group(2) or match.group(5) or "", int(explicit) if explicit else None


def _block_scalar(match: re.Match, lines: list[str]) -> str:
    """A `|` (literal) or `>` (folded) description as YAML reads it, with its
    chomping indicator: `-` strips the final newline, `+` keeps every
    trailing empty line, none keeps one."""
    style, chomp, indent = _header(match)
    body = _block_body(lines, indent)
    content = body[: max((i + 1 for i, line in enumerate(body) if line), default=0)]
    text = "\n".join(content) if style == "|" else _fold(content)
    if not text or chomp == "-":
        return text
    return text + "\n" * (1 + (len(body) - len(content) if chomp == "+" else 0))


def install_cost(skills_dir: Path, names: list[str], prompt: Path | None) -> Cost:
    """The names and descriptions of the installed skills, and the prompt file."""
    chars = sum(len(name) + len(description(skills_dir / name / "SKILL.md")) for name in names)
    try:
        prompt_chars = len(prompt.read_text(encoding="utf-8")) if prompt is not None else 0
    except (OSError, ValueError):
        prompt_chars = 0
    return Cost(len(names), chars, prompt_chars)


def _normal(text: str) -> str:
    return " ".join(text.split())


def shortened(skills_dir: Path, listed: dict[str, str | None]) -> list[tuple[str, int, int]]:
    """(skill, characters shown, characters written) for each description the
    agent shows shorter than the skill's own. None means the agent does not
    say, and an unreadable SKILL.md has nothing to compare."""
    cut = []
    for name, shown in sorted(listed.items()):
        full = _normal(description(skills_dir / name / "SKILL.md"))
        if shown is not None and full and len(_normal(shown)) < len(full):
            cut.append((name, len(_normal(shown)), len(full)))
    return cut


# Text that is different every release or every day. An ISO date and this
# registry's own version are exactly that; another project's version (the
# YAML 1.2.2 a description names) is content, and is left alone.
DATE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")


def registry_version(root: Path) -> str | None:
    try:
        return str(json.loads((root / "index.json").read_text(encoding="utf-8"))["registry_version"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def volatile(text: str, version: str | None) -> list[str]:
    """Dates, and this registry's version, found in `text`."""
    found = DATE.findall(text)
    if version:
        found += re.findall(rf"(?<![\w.])v?{re.escape(version)}(?![\w.])", text)
    return found


def volatile_problems(label: str, text: str, version: str | None) -> list[str]:
    """Why always-loaded text would break a provider's prompt cache, or []."""
    hits = volatile(text, version)
    if not hits:
        return []
    return [(f"{label} holds {', '.join(hits)}, which changes between releases; it is read in every "
             "session, so a changing value breaks the provider's prompt cache for everything after it")]
