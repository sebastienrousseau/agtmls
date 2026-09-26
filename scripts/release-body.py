#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Write a GitHub release body in the portfolio's Release Page Format.

Only the Highlights are written by hand, in the prepared notes, before the
tag is pushed. Everything else is composed here once the workflow has built:

    ## Highlights ⭐️      the prepared notes' section
    ## What's Changed     GitHub's generate-notes output, one line per PR
    ## New Contributors   the same, only when there are any
    ## Checksums          the SHA256SUMS the workflow just wrote
    **Full Changelog**: <compare URL>

A range with no pull requests (usually the first tag) lists its commits in
the same `* <subject> by @<author> in <url>` shape, from `--commits`. A
release with no prepared notes fails here, rather than shipping the one-line
default v0.0.1-v0.0.5 went out with.

    python3 scripts/release-body.py --tag v<version> --notes-dir docs/release-notes \\
        --sums dist/release/SHA256SUMS --generated generated.md \\
        [--commits commits.json] --out body.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.release_notes import (
    CHANGED,
    CHECKSUMS,
    CONTRIBUTORS,
    FULL_CHANGELOG,
    HIGHLIGHTS,
    highlight_problems,
    section,
)

COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)


def commit_lines(commits: list[dict]) -> str:
    """`* <subject> by @<author> in <url>` for each commit of a range."""
    lines = []
    for item in commits:
        subject = item["commit"]["message"].splitlines()[0]
        author = (item.get("author") or {}).get("login") or item["commit"]["author"]["name"]
        lines.append(f"* {subject} by @{author} in {item['html_url']}")
    return "\n".join(lines)


def body(notes: str, sums: str, generated: str, commits: list[dict] | None = None) -> str:
    generated = COMMENTS.sub("", generated)
    changed = section(generated, CHANGED)
    if not (changed or "").strip():
        if not commits:
            raise ValueError(f"the generated notes have no `## {CHANGED}` and no --commits were given")
        changed = commit_lines(commits)
    full = next((line for line in generated.splitlines() if FULL_CHANGELOG.match(line.strip())), None)
    if full is None:
        raise ValueError("the generated notes have no `**Full Changelog**` line")
    parts = [f"## {HIGHLIGHTS}\n\n{section(notes, HIGHLIGHTS).strip()}", f"## {CHANGED}\n\n{changed.strip()}"]
    contributors = section(generated, CONTRIBUTORS)
    if (contributors or "").strip():
        parts.append(f"## {CONTRIBUTORS}\n\n{contributors.strip()}")
    parts.append(f"## {CHECKSUMS}\n\n```\n{sums.rstrip()}\n```")
    parts.append(full.strip())
    return "\n\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--notes-dir", type=Path, required=True)
    parser.add_argument("--sums", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True,
                        help="the body GitHub's releases/generate-notes returned")
    parser.add_argument("--commits", type=Path,
                        help="the range's commits as the GitHub API lists them, for a range without PRs")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    notes = args.notes_dir / f"{args.tag}.md"
    if not notes.is_file():
        print(f"FAIL: no release notes at {notes}; write them before releasing (see RELEASE.md)")
        return 1
    text = notes.read_text(encoding="utf-8")
    problems = highlight_problems(notes.name, text)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    commits = json.loads(args.commits.read_text(encoding="utf-8")) if args.commits else None
    try:
        composed = body(
            text, args.sums.read_text(encoding="utf-8"), args.generated.read_text(encoding="utf-8"), commits
        )
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1
    args.out.write_text(composed, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
