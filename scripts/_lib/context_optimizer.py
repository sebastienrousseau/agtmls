# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Agent context and markdown optimizer for AgtMLS.

Finds conversational filler and volatile timestamps in always-loaded
instructions, counts list and table lines, and formats Repomix-compatible
context packs, without third-party dependencies.

It reports and never rewrites prose: deleting "in order to" or a whole
timestamped line can drop or change an instruction. The one rewrite is
collapsing runs of blank lines, which carries no meaning.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

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
# A date-time is volatile only if it changes; this cannot tell, so it says so.
VOLATILE_NOTE = ("timestamp in the first 50 lines: if it changes between sessions, "
                 "the provider cannot reuse the cached prompt prefix after it")
# A fenced code block, opening to closing fence, or to the end when unclosed.
FENCED = re.compile(r"(^(?:```|~~~)[^\n]*\n.*?(?:^(?:```|~~~)[ \t]*$|\Z))", re.MULTILINE | re.DOTALL)
TIMESTAMP_PATTERN = re.compile(r"\b202[4-9]-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def collapse_blank_lines(markdown_text: str) -> str:
    """Runs of blank lines collapsed to one, outside fenced code (``` or ~~~),
    where a blank line can be part of what an example shows: the only
    rewrite optimize makes. An unclosed fence keeps the rest as it is."""
    parts = FENCED.split(markdown_text)
    return "".join(part if index % 2 else MULTI_NEWLINES.sub("\n\n", part) for index, part in enumerate(parts))


def findings(markdown_text: str) -> list[str]:
    """`<line>: <what>` for each filler phrase, and each timestamp in the
    first 50 lines (it changes every build, so the provider's prompt cache
    can never reuse the prefix after it). Sorted by line."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(markdown_text.splitlines(), start=1):
        found += [(number, f"filler phrase {m.group()!r}") for pat in PADDING_PATTERNS for m in pat.finditer(line)]
        if number <= 50 and TIMESTAMP_PATTERN.search(line):
            found.append((number, VOLATILE_NOTE))
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
    summary = f"{estimate_tokens(text)} tokens, {structured_line_density(text)} list/table lines per 100 tokens"
    return 0, [*lines, f"OK: {name}: {summary}{tail}"], None


def estimate_tokens(text: str) -> int:
    """The registry's one token estimate, `context_cost.approx_tokens`
    (characters / 4, rounded up): approximate, never a tokenizer count."""
    return approx_tokens(len(text))


def structured_line_density(markdown_text: str) -> float:
    """List and table lines per 100 estimated tokens. A formatting measure:
    it counts lines shaped like rules, not whether they are rules, correct,
    or useful. Measured uplift says whether a skill helps; this does not."""
    tokens = estimate_tokens(markdown_text)
    if tokens == 0:
        return 0.0
    directives = len(re.findall(r"^(?:[-*]|\d+\.|\s*\|)\s+\S+", markdown_text, re.MULTILINE))
    return round((directives * 100) / tokens, 2)


def escape(text: str) -> str:
    """XML character data: `&`, `<` and `>` escaped. Written out rather than
    imported: xml.sax.saxutils loads urllib.request and http.client, about
    27 ms on every CLI start, since agtmls.py imports this module."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def quoteattr(text: str) -> str:
    """A double-quoted XML attribute value, as xml.sax.saxutils.quoteattr
    writes one when the value holds a double quote."""
    text = escape(text).replace('"', "&quot;")
    return '"' + text.replace("\n", "&#10;").replace("\r", "&#13;").replace("\t", "&#9;") + '"'


class Pack(NamedTuple):
    """A context pack and what did not fit it. Token counts are the registry's
    approximate estimate (`estimate_tokens`), never a tokenizer count."""

    xml: str            # "" when no pack can be produced
    omitted: list[str]  # optional files left out, in input order
    missing: list[str]  # required files that did not fit
    tokens: int         # estimated tokens of `xml` as rendered
    error: str = ""     # why no pack was produced, when not a missing file


_HEAD = '<context_pack version="1.0" generator="agtmls">'
_TAIL = "</context_pack>"


def _block(name: str, content: str) -> str:
    """One file as it appears in the pack. `tokens` is the file's own content
    estimate; the budget is measured on the rendered block."""
    lines = [f'  <file path={quoteattr(name)} tokens="{estimate_tokens(content)}">']
    lines += [f"    {escape(line)}" for line in content.splitlines()]
    lines.append("  </file>")
    return "\n".join(lines)


def _note(max_tokens: int, omitted: list[str]) -> str:
    names = escape(", ".join(omitted)).replace("--", "- -")
    return f"  <!-- omitted over the {max_tokens}-token budget: {names} -->"


def _cost(part: str) -> int:
    """A rendered part with its line break. Summed over the parts this bounds
    the whole pack's estimate from above, since each part rounds up."""
    return estimate_tokens(part + "\n")


def _render(blocks: list[tuple[int, str, str]], omitted: list[str], max_tokens: int | None) -> Pack:
    parts = [_HEAD, *(block for _, _, block in blocks)]
    parts += [_note(max_tokens, omitted)] if omitted else []
    xml = "\n".join([*parts, _TAIL])
    return Pack(xml, omitted, [], estimate_tokens(xml))


def _select(blocks: list[tuple[int, str, str]], budget: int, required: frozenset[str]):
    """(kept, omitted, missing, used): each file whole while it fits, required
    files first so an optional file listed earlier cannot spend their budget;
    kept and omitted stay in input order."""
    kept, omitted, missing, used = [], [], [], 0
    for index, name, block in sorted(blocks, key=lambda entry: entry[1] not in required):
        cost = _cost(block)
        if used + cost <= budget:
            kept.append((index, name, block))
            used += cost
        else:
            (missing if name in required else omitted).append((index, name))
    return sorted(kept), sorted(omitted), sorted(missing), used


def _names(entries) -> list[str]:
    return [entry[1] for entry in entries]


def _fit_note(kept: list, left: list, used: int, budget: int, max_tokens: int,
              required: frozenset[str]) -> list | None:
    """Leave out optional files, last first, until the note naming every
    omitted file fits too; None when only required files are left."""
    while left and used + _cost(_note(max_tokens, _names(left))) > budget:
        optional = [entry for entry in kept if entry[1] not in required]
        if not optional:
            return None
        kept.remove(optional[-1])
        used -= _cost(optional[-1][2])
        left = sorted([*left, optional[-1][:2]])
    return left


def build_pack(items: Sequence[tuple[str, str]], max_tokens: int | None = None,
               required: frozenset[str] = frozenset()) -> Pack:
    """Pack files into a Repomix-compatible XML block within `max_tokens`.

    The budget covers the whole rendered pack: wrapper, paths, escaping,
    indentation and the note naming omitted files. A file that does not fit is
    left out whole, never cut. A `required` file that does not fit means no
    pack at all, since a pack without its instructions is not a smaller pack
    but a different one. Content and paths are escaped: skill text is
    untrusted, and a `</file>` in it must not end its element.
    """
    blocks = [(index, name, _block(name, content)) for index, (name, content) in enumerate(items)]
    if max_tokens is None:
        return _render(blocks, [], None)
    budget = max_tokens - _cost(_HEAD) - _cost(_TAIL)
    if budget < 0:
        return Pack("", [name for _, name, _ in blocks], [], 0,
                    f"the {max_tokens}-token budget is smaller than an empty pack")
    kept, left, missing, used = _select(blocks, budget, required)
    if missing:
        return Pack("", _names(left), _names(missing), 0)
    fitted = _fit_note(kept, left, used, budget, max_tokens, required)
    if fitted is None:
        what = "fits the required file(s) but not" if required & set(_names(kept)) else "leaves no room for"
        return Pack("", _names(left), [], 0,
                    f"the {max_tokens}-token budget {what} the note naming the {len(left)} file(s) left out")
    return _render(kept, _names(fitted), max_tokens)


def pack_verdict(pack: Pack, max_tokens: int | None, allow_partial: bool) -> tuple[int, list[str]]:
    """(exit code, stderr lines) for a pack: nothing is written on failure."""
    if pack.error:
        return 1, [f"FAIL: {pack.error}; nothing written"]
    if pack.missing:
        return 1, [(f"FAIL: required file(s) do not fit the {max_tokens}-token budget: "
                    f"{', '.join(pack.missing)}; nothing written")]
    left = f"{len(pack.omitted)} file(s) do not fit the {max_tokens}-token budget: {', '.join(pack.omitted)}"
    if pack.omitted and not allow_partial:
        return 1, [f"FAIL: {left}; nothing written (--allow-partial writes the pack without them)"]
    return 0, [f"WARN: partial pack, {left}"] if pack.omitted else []


def write_text_atomic(path: Path, text: str) -> None:
    """Replace `path` with `text` in one step: a reader sees the old file or
    the new one, never half of either, and a failure leaves the old file."""
    import tempfile

    # Through a symlink to its target, as a plain write goes; and a file a
    # plain write could not open is refused rather than replaced.
    path = path.resolve() if path.is_symlink() else path
    if path.exists() and not os.access(path, os.W_OK):
        raise PermissionError(f"{path} is not writable")
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp, _mode_for(path))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _mode_for(path: Path) -> int:
    """The existing file's mode, or what a plain write would create."""
    if path.exists():
        return path.stat().st_mode & 0o777
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask
