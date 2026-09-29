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

# A rough English average. Every figure built on it is labelled "about".
CHARS_PER_TOKEN = 4
FRONTMATTER = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)
DESCRIPTION = re.compile(r"^description:[ \t]*(.*)$", re.MULTILINE)


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
    block = FRONTMATTER.match(text)
    field = DESCRIPTION.search(block.group(1)) if block else None
    return _unquote(field.group(1).strip()) if field else ""


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
