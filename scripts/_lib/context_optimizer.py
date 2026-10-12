# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Agent context and markdown optimizer for AgtMLS.

Prunes conversational noise, measures instruction density, enforces static
cache-friendly prefixes, and formats Repomix-compatible context packs
without third-party dependencies.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

# Conversational boilerplate patterns to prune
PADDING_PATTERNS = (
    re.compile(r"(?i)\bplease\s+(?:make\s+sure\s+to|ensure\s+that\s+you|note\s+that)\b\s*"),
    re.compile(r"(?i)\bit\s+is\s+(?:very\s+)?important\s+to\b\s*"),
    re.compile(r"(?i)\balways\s+remember\s+to\b\s*"),
    re.compile(r"(?i)\bas\s+an\s+ai\s+(?:coding\s+)?assistant,?\s*"),
    re.compile(r"(?i)\bin\s+order\s+to\b\s*"),
)

MULTI_NEWLINES = re.compile(r"\n{3,}")
TIMESTAMP_PATTERN = re.compile(r"\b202[4-9]-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def prune_boilerplate(markdown_text: str) -> str:
    """Strip conversational filler while preserving technical rules."""
    text = markdown_text
    for pat in PADDING_PATTERNS:
        text = pat.sub("", text)
    res = MULTI_NEWLINES.sub("\n\n", text)
    if markdown_text.endswith("\n") and not res.endswith("\n"):
        res += "\n"
    return res


def estimate_tokens(text: str) -> int:
    """Deterministic token estimation (approx 3.8 characters per token)."""
    if not text:
        return 0
    return max(1, int(len(text) / 3.8))


def instruction_density(markdown_text: str) -> float:
    """Calculate the ratio of bulleted/table constraints to total tokens."""
    tokens = estimate_tokens(markdown_text)
    if tokens == 0:
        return 0.0
    directives = len(re.findall(r"^(?:[-*]|\d+\.|\s*\|)\s+\S+", markdown_text, re.MULTILINE))
    return round((directives * 100) / tokens, 2)


def enforce_cache_friendly_prefix(markdown_text: str) -> str:
    """Ensure no volatile ISO timestamps exist in the top 50 lines."""
    lines = markdown_text.splitlines()
    prefix_lines = []
    for line in lines[:50]:
        if TIMESTAMP_PATTERN.search(line):
            continue
        prefix_lines.append(line)
    prefix_lines.extend(lines[50:])
    res = "\n".join(prefix_lines)
    if markdown_text.endswith("\n") and not res.endswith("\n"):
        res += "\n"
    return res


def pack_repomix_xml(
    items: Sequence[tuple[str, str]],
    max_tokens: int | None = None,
) -> str:
    """Pack file items into a structured Repomix-compatible XML context block."""
    out = ['<context_pack version="1.0" generator="agtmls">']
    used_tokens = 0
    for name, content in items:
        est = estimate_tokens(content)
        if max_tokens is not None and (used_tokens + est) > max_tokens:
            out.append(f'  <!-- Truncated: {name} exceeds budget of {max_tokens} tokens -->')
            break
        used_tokens += est
        out.append(f'  <file path="{name}" tokens="{est}">')
        for line in content.splitlines():
            out.append(f"    {line}")
        out.append("  </file>")
    out.append("</context_pack>")
    return "\n".join(out)
