#!/usr/bin/env python3
"""Port (TARGET): dedupe a colon-separated PATH string, preserving first
occurrence and dropping empty segments.

Idiomatic Python: split on ``":"`` and use an insertion-ordered ``dict`` as
an ordered set. None of the Bash source's hazards exist here — no
word-splitting, no glob expansion, no ``IFS`` state, no quoting pitfalls.

Contract matches ``reference.sh`` exactly: one PATH string per stdin line;
print the cleaned string per line (an all-empty input yields an empty line).
"""

import sys


def dedupe_path(path: str) -> str:
    seen: dict[str, None] = {}
    for seg in path.split(":"):
        if seg and seg not in seen:
            seen[seg] = None
    return ":".join(seen)


def main() -> int:
    for line in sys.stdin:
        print(dedupe_path(line.rstrip("\n")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
