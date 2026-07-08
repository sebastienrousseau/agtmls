#!/usr/bin/env python3
"""Port (TARGET): word-frequency histogram.

Idiomatic Python: ``str.split()`` (splits on whitespace runs and drops
empties in one call), ``collections.Counter`` for the tally, ``sorted`` for
order. Ruby's ``tally`` maps directly to ``Counter``; Ruby's
Enumerable/blocks map to comprehensions and iteration.

Contract matches ``reference.rb``: read all of stdin; output
"<word> <count>" per line, sorted by word ascending.
"""

import sys
from collections import Counter


def main() -> int:
    counts = Counter(sys.stdin.read().split())
    for word in sorted(counts):
        print(f"{word} {counts[word]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
