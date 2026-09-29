#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate AgtMLS system prompt profiles."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import context_cost  # noqa: E402  (scripts path first)

PROMPTS = ROOT / "system-prompts"
LANGUAGES = ["rust", "python", "go", "cpp", "swift", "typescript", "javascript", "ruby", "bash"]


def read_prompt(path: Path) -> str | None:
    """The prompt's text, or None when it is not UTF-8."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def base_problems() -> list[str]:
    base = PROMPTS / "_base.md"
    if not base.exists():
        return ["system-prompts/_base.md missing"]
    text = read_prompt(base)
    if text is None:
        return ["system-prompts/_base.md is not UTF-8 text"]
    if "# " not in text:
        return ["system-prompts/_base.md missing top-level heading"]
    # Every generated CLAUDE.md or AGENTS.md begins with this, in every session.
    return context_cost.volatile_problems("system-prompts/_base.md", text, context_cost.registry_version(ROOT))


def language_problems(lang: str) -> list[str]:
    path = PROMPTS / f"{lang}.md"
    if not path.exists():
        return [f"system-prompts/{lang}.md missing"]
    text = read_prompt(path)
    if text is None:
        return [f"system-prompts/{lang}.md is not UTF-8 text"]
    errors = [] if text.strip() else [f"system-prompts/{lang}.md is empty"]
    if "# " not in text:
        errors.append(f"system-prompts/{lang}.md missing top-level heading")
    return errors + context_cost.volatile_problems(f"system-prompts/{lang}.md", text, context_cost.registry_version(ROOT))


def main() -> int:
    errors = base_problems()
    for lang in LANGUAGES:
        errors += language_problems(lang)
    extras = sorted(
        p.name for p in PROMPTS.glob("*.md")
        if p.stem not in set(LANGUAGES) | {"_base"}
    )
    if extras:
        errors.append(f"unexpected system prompt profile(s): {', '.join(extras)}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} system prompt issue(s)")
        return 1
    print(f"OK: {len(LANGUAGES)} language profile(s) plus base prompt valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
