#!/usr/bin/env python3
"""Reference implementation (SOURCE): IBAN mod-97 validation.

Idiomatic Python: rearrange, expand letters to digits, build the whole
number as an arbitrary-precision ``int`` and take ``% 97``. This is correct
in Python precisely because ``int`` has no width limit.

Contract: read one IBAN per line from stdin; for each non-empty line print
``valid`` or ``invalid``. ASCII input; only the space character is stripped.
"""

import sys


def iban_is_valid(iban: str) -> bool:
    s = iban.replace(" ", "").upper()
    if not (15 <= len(s) <= 34) or not s.isalnum():
        return False
    if not (s[0].isalpha() and s[1].isalpha() and s[2].isdigit() and s[3].isdigit()):
        return False
    rearranged = s[4:] + s[:4]
    # A-Z -> 10..35, 0-9 -> 0..9  (base-36 digit value, rendered decimal)
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(digits) % 97 == 1


def main() -> int:
    for line in sys.stdin:
        line = line.rstrip("\n")
        if line == "":
            continue
        print("valid" if iban_is_valid(line) else "invalid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
