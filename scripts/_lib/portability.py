# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What stops one skill directory working the same in every agent.

Claude Code, Codex, Antigravity, Cursor, Copilot, Gemini CLI and OpenCode all
read `SKILL.md`, but not the same extras. These are the portability rules of
the AgtMLS Elevation Plan (section 11c), each a thing a skill does that one
agent honours and the others do not, or a budget the others enforce:

- Claude Code's command injection -- an inline code span right after `!`,
  or a fence opened with ```! -- runs a shell command before the skill is
  shown. Every other agent shows the literal text instead.
- `${CLAUDE_SKILL_DIR}` and the other `CLAUDE_*` variables are set only by
  Claude Code; elsewhere the path they build does not exist.
- Reference files are read one level deep from SKILL.md; a reference that
  sends the agent to a further reference is followed unevenly.
- The body loads whole on activation; past about 5,000 tokens (estimated at
  four characters a token) detail belongs in a reference file.

The authoring lint (validate-skills.py) fails on these; `audit --foreign`
reports them as notes, since they are not security findings.
"""

from __future__ import annotations

import re
from pathlib import Path

MAX_BODY_TOKENS = 5000
CHARS_PER_TOKEN = 4
SPAN = re.compile(r"`[^`\n]+`")
FENCE = re.compile(r"^[ \t]*```!", re.MULTILINE)
CLAUDE_VAR = re.compile(r"\$\{?CLAUDE_[A-Z_]+\}?")
LOCATED = re.compile(r"^(?P<where>[^\s:]+:\d+): (?P<what>.+)$")
CHAINED = re.compile(r"^(?P<source>\S+) links to (?P<target>\S+): keep references one level deep")
LINK = re.compile(r"\]\(([^)#\s]+)")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def body(text: str) -> str:
    """SKILL.md after its frontmatter (all of it when there is none)."""
    if not text.startswith("---"):
        return text
    parts = re.split(r"\n---[ \t]*\n", text, maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def claude_only(text: str) -> list[tuple[int, str]]:
    """(line, what) for each Claude Code-only construct in `text`."""
    found = []
    for match in SPAN.finditer(text):
        start = match.start()
        before = text[start - 2] if start >= 2 else ""
        if start >= 1 and text[start - 1] == "!" and not (before.isalnum() or before in "_`"):
            found.append((_line(text, start), f"`!{match.group()}` runs a command only in Claude Code"))
    for match in FENCE.finditer(text):
        found.append((_line(text, match.start()), "a ```! block runs commands only in Claude Code"))
    for match in CLAUDE_VAR.finditer(text):
        found.append((_line(text, match.start()), f"`{match.group()}` is set only by Claude Code"))
    return sorted(found)


def problems(skill_dir: Path) -> list[str]:
    """Every portability problem in one skill directory, as messages."""
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    tokens = len(body(text)) // CHARS_PER_TOKEN
    if tokens > MAX_BODY_TOKENS:
        errors.append(
            f"SKILL.md body is about {tokens} tokens; keep it under {MAX_BODY_TOKENS} "
            "and move detail into a reference file"
        )
    root = skill_dir.resolve()
    for path in sorted(p for p in skill_dir.rglob("*.md") if p.is_file()):
        rel = path.relative_to(skill_dir).as_posix()
        content = text if path == skill_md else path.read_text(encoding="utf-8", errors="replace")
        errors += [f"{rel}:{line}: {what}" for line, what in claude_only(content)]
        if path == skill_md:
            continue
        for target in LINK.findall(content):
            if SCHEME.match(target):
                continue  # a URL, not a file in the skill
            linked = (path.parent / target).resolve()
            if linked.suffix == ".md" and linked.name != "SKILL.md" and linked.is_relative_to(root):
                errors.append(
                    f"{rel} links to {linked.relative_to(root).as_posix()}: "
                    "keep references one level deep from SKILL.md"
                )
    return list(dict.fromkeys(errors))  # a construct repeated on one line is one problem


def summarize(messages: list[str], examples: int = 3) -> list[str]:
    """The same problems grouped by rule, for a report a person reads: a
    skill that bundles its docs can repeat one problem hundreds of times."""
    places: dict[str, list[str]] = {}
    chains: list[str] = []
    other: list[str] = []
    for message in messages:
        located = LOCATED.match(message)
        chained = CHAINED.match(message)
        if located:
            places.setdefault(located["what"], []).append(located["where"])
        elif chained:
            chains.append(f"{chained['source']} -> {chained['target']}")
        else:
            other.append(message)
    lines = list(other)
    for what, where in places.items():
        if len(where) == 1:
            lines.append(f"{where[0]}: {what}")
        else:
            lines.append(f"{what}: {len(where)} place(s), e.g. {', '.join(where[:examples])}")
    if len(chains) == 1:
        source, target = chains[0].split(" -> ")
        lines.append(f"{source} links to {target}: keep references one level deep from SKILL.md")
    elif chains:
        lines.append(
            f"{len(chains)} reference link(s) go more than one level deep from SKILL.md, "
            f"e.g. {', '.join(chains[:examples])}"
        )
    return lines
