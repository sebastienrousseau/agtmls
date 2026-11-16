# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Reading the `---` frontmatter at the top of SKILL.md, commands and agents.

Seven scripts each carried their own copy of the block pattern and the
top-level-key rule. This is the one copy. It reads the subset of YAML the
registry writes (top-level `key: value`, indented continuation lines, and
`|`/`>` block scalars) without a YAML dependency, because every script must
stay stdlib-only.

What a caller does with a value (join continuation lines with a space or a
newline, strip YAML quotes) differs on purpose and stays with the caller.
"""

from __future__ import annotations

import re

BLOCK = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)
TOP_KEY = re.compile(r"^([A-Za-z0-9_-]+):[ \t]*(.*)$")
# A value that only announces a block scalar carries no text of its own.
BLOCK_SCALARS = frozenset({"|", ">", "|-", ">-", "|+", ">+", ""})


def split(text: str) -> tuple[str, str] | None:
    """(the frontmatter block, the body after it), or None without one."""
    match = BLOCK.match(text)
    return (match.group(1), text[match.end():]) if match else None


def top_level(line: str) -> tuple[str, str] | None:
    """(key, value) when `line` starts a top-level field, else None."""
    match = TOP_KEY.match(line)
    if not match or line.startswith((" ", "\t")):
        return None
    return match.group(1), match.group(2).strip()


def grouped(block: str) -> dict[str, list[str]]:
    """Each top-level key with its value parts: the inline value (unless it
    only opens a block scalar), then every following line, stripped, until
    the next key. A later duplicate key replaces an earlier one."""
    fields: dict[str, list[str]] = {}
    key: str | None = None
    for line in block.split("\n"):
        started = top_level(line)
        if started is not None:
            key, value = started
            fields[key] = [] if value in BLOCK_SCALARS else [value]
        elif key is not None:
            fields[key].append(line.strip())
    return fields


def fields(text: str, joiner: str) -> dict[str, str] | None:
    """Every top-level field, its parts joined with `joiner`; None without a block."""
    parts = split(text)
    if parts is None:
        return None
    return {key: joiner.join(values).strip() for key, values in grouped(parts[0]).items()}


def line_value(text: str, key: str) -> str | None:
    """The rest of `key`'s first line, unstripped; None when absent."""
    parts = split(text)
    if parts is None:
        return None
    match = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", parts[0], re.MULTILINE)
    return match.group(1) if match else None
