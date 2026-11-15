# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Agent context and markdown optimizer for AgtMLS.

Finds conversational filler and volatile timestamps in always-loaded
instructions, measures instruction density, and formats Repomix-compatible
context packs, without third-party dependencies.

It reports and never rewrites prose: deleting "in order to" or a whole
timestamped line can drop or change an instruction. The one rewrite is
collapsing runs of blank lines, which carries no meaning.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from xml.sax.saxutils import escape, quoteattr

from _lib.context_cost import approx_tokens

# Conversational filler worth a second look; reported, never removed.
PADDING_PATTERNS = (
    re.compile(r"(?i)\bplease\s+(?:make\s+sure\s+to|ensure\s+that\s+you|note\s+that)\b\s*"),
    re.compile(r"(?i)\bit\s+is\s+(?:very\s+)?important\s+to\b\s*"),
    re.compile(r"(?i)\balways\s+remember\s+to\b\s*"),
    re.compile(r"(?i)\bas\s+an\s+ai\s+(?:coding\s+)?assistant,?\s*"),
    re.compile(r"(?i)\bin\s+order\s+to\b\s*"),
)

MULTI_NEWLINES = re.compile(r"\n{3,}")
TIMESTAMP_PATTERN = re.compile(r"\b202[4-9]-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def collapse_blank_lines(markdown_text: str) -> str:
    """Runs of blank lines collapsed to one: the only rewrite optimize makes."""
    return MULTI_NEWLINES.sub("\n\n", markdown_text)


def findings(markdown_text: str) -> list[str]:
    """`<line>: <what>` for each filler phrase, and each timestamp in the
    first 50 lines (it changes every build, so the provider's prompt cache
    can never reuse the prefix after it). Sorted by line."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(markdown_text.splitlines(), start=1):
        found += [(number, f"filler phrase {m.group()!r}") for pat in PADDING_PATTERNS for m in pat.finditer(line)]
        if number <= 50 and TIMESTAMP_PATTERN.search(line):
            found.append((number, "timestamp in the first 50 lines breaks the cached prompt prefix"))
    return [f"{number}: {what}" for number, what in sorted(found)]


def optimize(name: str, text: str, mode: str) -> tuple[int, list[str], str | None]:
    """What `optimize` says and does for a file: (exit code, lines to print,
    new text to write or None). `mode` is report, check or write; only write
    rewrites, and only runs of blank lines, since rewriting prose can change
    what an instruction says."""
    notes = findings(text)
    clean = collapse_blank_lines(text)
    lines = [f"{name}:{note}" for note in notes]
    tail = f"; {len(notes)} finding(s) left for you to edit" if notes else ""
    if mode == "check":
        ok = not notes and clean == text
        return (0 if ok else 1), [*lines, f"{'OK' if ok else 'FAIL'}: {name}{tail}"], None
    if mode == "write":
        done = "collapsed blank lines" if clean != text else "nothing to rewrite"
        return 0, [*lines, f"OK: {name}: {done}{tail}"], (clean if clean != text else None)
    summary = f"{estimate_tokens(text)} tokens, {instruction_density(text)}% density"
    return 0, [*lines, f"OK: {name}: {summary}{tail}"], None


def estimate_tokens(text: str) -> int:
    """The registry's one token estimate, `context_cost.approx_tokens`
    (characters / 4, rounded up): approximate, never a tokenizer count."""
    return approx_tokens(len(text))


def instruction_density(markdown_text: str) -> float:
    """Calculate the ratio of bulleted/table constraints to total tokens."""
    tokens = estimate_tokens(markdown_text)
    if tokens == 0:
        return 0.0
    directives = len(re.findall(r"^(?:[-*]|\d+\.|\s*\|)\s+\S+", markdown_text, re.MULTILINE))
    return round((directives * 100) / tokens, 2)


def pack_repomix_xml(
    items: Sequence[tuple[str, str]],
    max_tokens: int | None = None,
) -> tuple[str, list[str]]:
    """Pack file items into a Repomix-compatible XML block, and name the files
    left out because they did not fit `max_tokens`.

    Content and paths are escaped: skill text is untrusted, and a `</file>` in
    it must not end the element and let what follows pose as packer output.
    A file that does not fit is skipped, never cut, and named in the pack.
    """
    out = ['<context_pack version="1.0" generator="agtmls">']
    used_tokens = 0
    omitted: list[str] = []
    for name, content in items:
        est = estimate_tokens(content)
        if max_tokens is not None and used_tokens + est > max_tokens:
            omitted.append(name)
            continue
        used_tokens += est
        out.append(f"  <file path={quoteattr(name)} tokens=\"{est}\">")
        out.extend(f"    {escape(line)}" for line in content.splitlines())
        out.append("  </file>")
    if omitted:
        names = escape(", ".join(omitted)).replace("--", "- -")
        out.append(f"  <!-- omitted over the {max_tokens}-token budget: {names} -->")
    out.append("</context_pack>")
    return "\n".join(out), omitted
