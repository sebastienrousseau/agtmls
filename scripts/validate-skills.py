#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate every skills/**/SKILL.md against the AgtMLS skill contract.

Zero-dependency (stdlib only). Exits non-zero if any skill fails, so it can
gate CI. The router bets everything on frontmatter quality; this enforces it.

Per skill, checks the agentskills.io Agent Skills spec plus the stricter
AgtMLS router contract:

  spec (https://agentskills.io/specification.md)
  - a YAML frontmatter block (--- ... ---) that parses;
  - only the six specified keys — anything else fails validation;
  - `name` present, 1-MAX_NAME chars, kebab-case, no consecutive hyphens,
    and equal to the skill's directory name;
  - `description` present and <= MAX_DESC chars;
  - `compatibility`, when present, <= MAX_COMPAT chars;
  - `metadata`, when present, a mapping of string keys to string values;
  - body <= MAX_BODY_LINES lines, so activation stays inside the
    progressive-disclosure budget.

  AgtMLS additions
  - `description` contains a trigger cue (a "when"/"use for"/"trigger"
    phrase that tells the router when to load the skill);
  - a top-level `# ` heading in the body;
  - portability (_lib/portability.py): no Claude Code-only command
    injection or CLAUDE_* variables, references one level deep, and a body
    under about 5,000 tokens.

The idea (a validator guarding the skill catalog) is adopted from
addyosmani/agent-skills (MIT); this implementation is original.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MAX_DESC = 1024  # Claude Code silently truncates descriptions beyond this.
MAX_NAME = 64  # Spec cap on `name`.
MAX_COMPAT = 500  # Spec cap on `compatibility`.
MAX_BODY_LINES = 500  # Spec guidance: keep SKILL.md under 500 lines.

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import portability, skill_roots  # noqa: E402  (scripts path first)

SKILLS_DIR = ROOT / "skills"

# The spec's closed key set. A key outside this set fails validation in
# `skills-ref validate`, so it must fail here too or the catalog ships
# skills that other runtimes reject.
SPEC_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}

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


def name_problems(name: str, dirname: str) -> list[str]:
    if not name:
        return ["missing `name`"]
    errors = []
    if name != dirname:
        errors.append(f"`name` ({name!r}) != directory name ({dirname!r})")
    if not KEBAB.match(name):
        errors.append(f"`name` is not kebab-case: {name!r}")
    if len(name) > MAX_NAME:
        errors.append(f"`name` too long: {len(name)} > {MAX_NAME} chars")
    return errors


def compatibility_problems(compat: str | None) -> list[str]:
    if compat is None:
        return []
    flat_compat = re.sub(r"\s+", " ", compat).strip()
    if not flat_compat:
        return ["`compatibility` present but empty"]
    if len(flat_compat) > MAX_COMPAT:
        return [f"`compatibility` too long: {len(flat_compat)} > {MAX_COMPAT} chars"]
    return []


def metadata_problems(metadata: str | None) -> list[str]:
    if metadata is None:
        return []
    errors = [] if metadata.strip() else ["`metadata` present but empty"]
    for line in metadata.split("\n"):
        if line.strip() and not re.match(r"^[A-Za-z0-9_.-]+:[ \t]*\S", line.strip()):
            errors.append(f"`metadata` must be flat string key/value pairs: {line.strip()!r}")
    return errors


def description_problems(desc: str) -> list[str]:
    if not desc:
        return ["missing `description`"]
    errors = []
    flat = re.sub(r"\s+", " ", desc).strip()
    if len(flat) > MAX_DESC:
        errors.append(f"`description` too long: {len(flat)} > {MAX_DESC} chars")
    if not TRIGGER.search(desc):
        errors.append("`description` lacks a trigger cue (a 'when…' / 'use for' phrase)")
    return errors


def body_problems(text: str) -> list[str]:
    errors = []
    parts = re.split(r"\n---[ \t]*\n", text, maxsplit=1)
    body = parts[1] if len(parts) > 1 else ""
    if not re.search(r"^#[ \t]+\S", body, re.MULTILINE):
        errors.append("body has no top-level `# ` heading")

    lines = len(text.splitlines())
    if lines > MAX_BODY_LINES:
        errors.append(
            f"SKILL.md too long: {lines} > {MAX_BODY_LINES} lines "
            "(move detail into reference.md)"
        )
    return errors


def check(skill_md: Path) -> list[str]:
    errors: list[str] = []
    dirname = skill_md.parent.name
    text = skill_md.read_text(encoding="utf-8")

    fields, err = parse_frontmatter(text)
    if err:
        return [err]
    assert fields is not None

    unknown = sorted(set(fields) - SPEC_KEYS)
    if unknown:
        errors.append(
            "frontmatter key(s) outside the Agent Skills spec: "
            + ", ".join(f"`{key}`" for key in unknown)
        )

    errors += name_problems(fields.get("name", ""), dirname)
    errors += compatibility_problems(fields.get("compatibility"))
    errors += metadata_problems(fields.get("metadata"))
    errors += description_problems(fields.get("description", ""))
    errors += body_problems(text)
    errors += portability.problems(skill_md.parent)
    return errors


def main() -> int:
    skill_files = skill_roots.skill_files(ROOT)
    if not skill_files:
        print(f"no SKILL.md files found under {SKILLS_DIR}", file=sys.stderr)
        return 1

    problems = 0
    bundles = {}
    for sm in skill_files:
        meta = sm.parent / "metadata.json"
        bundles[sm.parent.name] = json.loads(meta.read_text(encoding="utf-8")).get("bundle") if meta.exists() else None
    for error in skill_roots.problems(ROOT, bundles):
        problems += 1
        print(f"✗ layout: {error}")
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
