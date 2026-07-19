#!/usr/bin/env python3
"""Create a local, redacted skill proposal from a session transcript.

This is the first step of a safe skill-evolution loop: observe explicitly
provided work, redact likely secrets, summarize repeated signals, and stage a
proposal for human review. It never publishes or installs the result.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / ".agtmls" / "proposals"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?([A-Za-z0-9._/\-+=]{12,})"),
    re.compile(r"\b(?:sk|ghp|gho|github_pat)_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b"),
]
COMMAND = re.compile(r"^\s*(?:\$|>)\s+(.+)$", re.MULTILINE)
PATHISH = re.compile(r"\b(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\b")
WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: m.group(0).replace(m.group(2), "[REDACTED]") if m.lastindex else "[REDACTED]", redacted)
    return redacted


def top_terms(text: str) -> list[str]:
    stop = set(
        "the and for with that this from into have need when what how why you your are was were not but can"
        .split()
    )
    words = [w.lower() for w in WORD.findall(text) if w.lower() not in stop]
    return [term for term, _ in Counter(words).most_common(20)]


def render(name: str, transcript: str) -> str:
    clean = redact(transcript)
    commands = COMMAND.findall(clean)
    paths = PATHISH.findall(clean)
    terms = top_terms(clean)
    description = (
        f"Draft proposal for a reusable AgtMLS skill. Use when future sessions repeat "
        f"the workflow observed in this transcript around {', '.join(terms[:5]) or name}."
    )
    return f"""<!-- SPDX-FileCopyrightText: {date.today().year} Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Skill Proposal: {name}

Status: draft, human review required
Date: {date.today().isoformat()}

## Candidate frontmatter

```yaml
---
name: {name}
description: >-
  {description}
---
```

## Observed signals

- Top terms: {', '.join(terms) if terms else 'none'}
- Commands seen: {len(commands)}
- Paths seen: {len(paths)}

## Commands

```text
{chr(10).join(commands[:40]) if commands else '(none detected)'}
```

## Referenced paths

```text
{chr(10).join(sorted(set(paths))[:80]) if paths else '(none detected)'}
```

## Proposed next step

Turn this proposal into `skills/{name}/SKILL.md` only after a maintainer
confirms the trigger, safety boundaries, and validation evidence. Add
`evals/cases/{name}.json` in the same change.

## Redacted transcript excerpt

```text
{clean[:12000]}
```
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--skill-name", required=True, help="kebab-case candidate skill name")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", args.skill_name):
        print("FAIL: --skill-name must be kebab-case", file=sys.stderr)
        return 1
    if not args.transcript.exists():
        print(f"FAIL: transcript not found: {args.transcript}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{args.skill_name}.md"
    out.write_text(render(args.skill_name, args.transcript.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
