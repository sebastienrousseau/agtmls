# Worked port — Bash → Python: PATH dedupe

Fleet domain: dotfiles / shell tooling (`dotfiles`, `pipelines`, `devkit`).

## What this teaches

**The Bash word-splitting / glob landmine (`reference.md` §R2 Bash, §R4).**
The "obvious" split — `for seg in $path` with `IFS=:` — also subjects the
unquoted `$path` to **pathname (glob) expansion**: a segment like `/tmp/*`
would silently expand against the current directory. The corpus includes
exactly that input, and `verify.sh` asserts it stays literal.

The safe Bash idiom is `IFS=':' read -ra parts` (array split, no globbing).
The Python port sidesteps the whole class: `str.split(":")` has no IFS
state, no word-splitting, and no glob expansion. Porting Bash → Python here
means **replacing implicit shell behaviour with explicit, hazard-free
operations** — and keeping outputs byte-identical while doing it.

Idiom shift: an insertion-ordered `dict` is Python's idiomatic ordered set
(`seen[seg] = None` … `":".join(seen)`), replacing the Bash `case`-on-a
`:$seen:` sentinel string.

## Files

| File | Role |
|---|---|
| `reference.sh` | SOURCE — idiomatic, hazard-safe Bash (`read -ra`) |
| `port.py` | TARGET — idiomatic Python (ordered-dict set) |
| `corpus/input.txt` | inputs incl. dups, empty segments, leading/trailing colon, and a `/tmp/*` glob probe |
| `corpus/expected.txt` | golden output, produced by the SOURCE |
| `verify.sh` | differential proof: source reproduces golden **and** port matches it |

## Run it

```sh
./verify.sh                 # equivalence proof (source vs port)
shellcheck reference.sh     # Bash land-green
ruff check port.py          # Python land-green
```

Current status: **source and port agree on all 8 corpus inputs; `/tmp/*`
proven to stay literal; shellcheck / shfmt / ruff clean.**

## Contract

One PATH string per stdin line. Print the deduped string per line
(preserve first occurrence, drop empty segments). An all-empty input line
yields an empty output line.
