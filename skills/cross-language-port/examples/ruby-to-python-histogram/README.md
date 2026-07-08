# Worked port — Ruby → Python: word histogram

Fleet domain: Ruby (`homebrew-tap`) → Python.

## What this teaches

**Enumerable pipeline + blocks → comprehensions/`Counter` (`reference.md`
§R2 Ruby, §R1.4).** Idiomatic Ruby is a chained Enumerable pipeline —
`split(/\s+/).reject(&:empty?).tally.sort` — driven by blocks. The idiomatic
Python port maps `tally` → `collections.Counter`, the block pipeline →
`str.split()` + `sorted`, and `each { |w, n| puts … }` → a `for` loop. The
port is not a line-by-line copy; it re-expresses the same computation in
Python's idiom.

**The subtle equivalence trap it catches:** sort order. The corpus includes
capitalised `Zebra`, which sorts **before** lowercase words (`Z`=0x5A <
`a`=0x61). Ruby's `String#<=>` and Python's `sorted` both order by codepoint
for ASCII, so they agree — but a port that lower-cased on one side only would
diverge. The golden corpus pins it.

## Files

| File | Role |
|---|---|
| `reference.rb` | SOURCE — idiomatic Ruby Enumerable pipeline (`tally`) |
| `port.py` | TARGET — idiomatic Python (`Counter` + `sorted`) |
| `corpus/` | multi-line text with repeats and a mixed-case sort probe |
| `verify.sh` | differential proof: source reproduces golden **and** port matches |

## Run it

```sh
./verify.sh              # equivalence proof
ruby -c reference.rb     # Ruby syntax check (rubocop for full land-green)
ruff check port.py       # Python land-green
```

Status: **source and port agree on all corpus words; ruby -c + ruff clean.**
