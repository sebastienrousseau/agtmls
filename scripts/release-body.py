#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Write a GitHub release body: the prepared notes plus the real checksums.

Release notes are written before the tag is pushed, and the artifacts are
built after it, so the notes cannot carry the checksums themselves. The
release workflow runs this once it has built: the notes' Checksums section is
replaced by the SHA256SUMS it just wrote. A release with no prepared notes
fails here, rather than shipping the one-line default v0.0.1-v0.0.5 went out
with.

    python3 scripts/release-body.py --tag v<version> --notes-dir docs/release-notes \\
        --sums dist/release/SHA256SUMS --out body.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CHECKSUMS = re.compile(r"^## Checksums[ \t]*\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
COMMENT = re.compile(r"\A(?:<!--.*?-->\s*)+", re.DOTALL)


def body(notes: str, sums: str) -> str:
    block = f"## Checksums\n\n```\n{sums.rstrip()}\n```\n"
    # The SPDX comment header is repository metadata, not part of the notes.
    notes = COMMENT.sub("", notes)
    if CHECKSUMS.search(notes):
        return CHECKSUMS.sub(lambda _: block + "\n", notes).rstrip() + "\n"
    return notes.rstrip() + "\n\n" + block


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--notes-dir", type=Path, required=True)
    parser.add_argument("--sums", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    notes = args.notes_dir / f"{args.tag}.md"
    if not notes.is_file():
        print(f"FAIL: no release notes at {notes}; write them before releasing (see RELEASE.md)")
        return 1
    args.out.write_text(
        body(notes.read_text(encoding="utf-8"), args.sums.read_text(encoding="utf-8")), encoding="utf-8"
    )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
