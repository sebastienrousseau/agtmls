#!/usr/bin/env python3
"""Reference (SOURCE): parse a duration like "1h30m45s" into seconds.

Idiomatic Python: validate with a regex and ``raise ValueError`` on bad
input; the caller uses ``try/except``. The Go port must turn each raise
into a returned ``error`` — Go has no exceptions and no sum types, so the
control flow inverts from "throw and catch" to "return and check".

Contract: one duration per stdin line -> integer seconds, or
"ERROR: <reason>".
"""

import re
import sys

UNIT = {"h": 3600, "m": 60, "s": 1}


def parse_duration(s: str) -> int:
    if not re.fullmatch(r"(\d+[hms])+", s):
        raise ValueError("empty" if s == "" else f"invalid duration: {s}")
    return sum(int(n) * UNIT[u] for n, u in re.findall(r"(\d+)([hms])", s))


def main() -> int:
    for line in sys.stdin:
        line = line.rstrip("\n")
        if line == "":
            continue
        try:
            print(parse_duration(line))
        except ValueError as e:
            print(f"ERROR: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
