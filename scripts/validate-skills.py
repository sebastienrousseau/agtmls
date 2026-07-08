#!/usr/bin/env python3
"""Validate every skills/**/SKILL.md against the AgtMLS skill contract.

Zero-dependency (stdlib only). Exits non-zero if any skill fails, so it can
gate CI. The router bets everything on frontmatter quality; this enforces it.

Per skill, checks:
  - a YAML frontmatter block (--- ... ---) that parses;
  - `name` present, kebab-case, and equal to the skill's directory name;
  - `description` present, <= MAX_DESC chars (Claude Code truncates beyond
    this), and containing a trigger cue (a "when"/"use for"/"trigger" phrase
    that tells the router when to load the skill);
  - a top-level `# ` heading in the body.

The idea (a validator guarding the skill catalog) is adopted from
addyosmani/agent-skills (MIT); this implementation is original.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_DESC = 1024  # Claude Code silently truncates descriptions beyond this.

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# A trigger cue: something that tells the router WHEN to load the skill
# ("… when X", "load before Y", "use for Z", "triggers: …").
TRIGGER = re.compile(
    r"\bwhen\b|\bbefore\b|\btrigger\b|\buse for\b|\buse this\b|\bload this\b",
    re.IGNORECASE,
)
BLOCK_SCALAR = {"|", ">", "|-", ">-", "|+", ">+", ""}


def parse_frontmatter(text: str) -> tuple[dict[str, str] | None, str | None]:
    """Return (fields, error). Minimal top-level key: value extraction that
    handles inline, folded (>), and literal (|) scalars — enough for the
    `name`/`description` contract without a YAML dependency."""
    if not text.startswith("---"):
        return None, "no frontmatter block (must start with '---')"
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    if not m:
        return None, "unterminated frontmatter block"
    fields: dict[str, str] = {}
    key: str | None = None
    buf: list[str] = []
    for line in m.group(1).split("\n"):
        top = re.match(r"^([A-Za-z0-9_-]+):[ \t]*(.*)$", line)
        if top and not line.startswith((" ", "\t")):
            if key is not None:
                fields[key] = "\n".join(buf).strip()
            key = top.group(1)
            val = top.group(2).strip()
            buf = [] if val in BLOCK_SCALAR else [val]
        elif key is not None:
            buf.append(line.strip())
    if key is not None:
        fields[key] = "\n".join(buf).strip()
    return fields, None


def check(skill_md: Path) -> list[str]:
    errors: list[str] = []
    dirname = skill_md.parent.name
    text = skill_md.read_text(encoding="utf-8")

    fields, err = parse_frontmatter(text)
    if err:
        return [err]
    assert fields is not None

    name = fields.get("name", "")
    if not name:
        errors.append("missing `name`")
    else:
        if name != dirname:
            errors.append(f"`name` ({name!r}) != directory name ({dirname!r})")
        if not KEBAB.match(name):
            errors.append(f"`name` is not kebab-case: {name!r}")

    desc = fields.get("description", "")
    if not desc:
        errors.append("missing `description`")
    else:
        flat = re.sub(r"\s+", " ", desc).strip()
        if len(flat) > MAX_DESC:
            errors.append(f"`description` too long: {len(flat)} > {MAX_DESC} chars")
        if not TRIGGER.search(desc):
            errors.append("`description` lacks a trigger cue (a 'when…' / 'use for' phrase)")

    parts = re.split(r"\n---[ \t]*\n", text, maxsplit=1)
    body = parts[1] if len(parts) > 1 else ""
    if not re.search(r"^#[ \t]+\S", body, re.MULTILINE):
        errors.append("body has no top-level `# ` heading")

    return errors


def main() -> int:
    skill_files = sorted(SKILLS_DIR.glob("**/SKILL.md"))
    if not skill_files:
        print(f"no SKILL.md files found under {SKILLS_DIR}", file=sys.stderr)
        return 1

    problems = 0
    for sm in skill_files:
        rel = sm.parent.relative_to(ROOT)
        errs = check(sm)
        if errs:
            problems += len(errs)
            print(f"✗ {rel}")
            for e in errs:
                print(f"    - {e}")
        else:
            print(f"✓ {rel}")

    print()
    if problems:
        print(f"FAIL: {problems} problem(s) across {len(skill_files)} skill(s)")
        return 1
    print(f"OK: {len(skill_files)} skill(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
