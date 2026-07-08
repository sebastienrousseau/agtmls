#!/usr/bin/env python3
"""Reference (SOURCE): parse a #RRGGBB hex colour into "r g b" decimals.

Idiomatic Python: validate with a regex and ``raise ValueError`` on bad
input; the caller uses ``try/except``. The C++ port returns
``std::expected`` instead — the error becomes a value, not an exception —
and relies on RAII (``std::string``, no ``new``/``delete``).

Contract: one colour per stdin line -> "r g b", or "ERROR: <reason>".
"""

import re
import sys


def parse_color(s: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", s):
        raise ValueError(f"invalid colour: {s}")
    return int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)


def main() -> int:
    for line in sys.stdin:
        line = line.rstrip("\n")
        if line == "":
            continue
        try:
            r, g, b = parse_color(line)
            print(f"{r} {g} {b}")
        except ValueError as e:
            print(f"ERROR: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
