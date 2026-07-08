# Worked port — Python → Go: duration parser

Fleet domain: Python services (`pain001`, `akande`, the `*-mcp` servers) → Go.

## What this teaches

**Exceptions → returned errors, no sum types (`reference.md` §R2 Go,
§R1.2).** Python validates and `raise ValueError`; the caller uses
`try/except`. Go has no exceptions: the port returns `(int, error)` and the
caller writes `if err != nil`. The control flow **inverts** — nothing
throws; every failure is a value that must be handled at the call site.
Python's `sum(...)` generator expression becomes an explicit `for` +
accumulator; the `re.fullmatch` guard becomes an anchored `regexp`.

Because Go lacks sum types, the "valid vs error" outcome is modelled with
the idiomatic `(value, error)` pair rather than a tagged union — exactly the
translation the skill flags for Python/Rust → Go ports.

## Files

| File | Role |
|---|---|
| `reference.py` | SOURCE — idiomatic Python, `raise ValueError` |
| `port.go` | TARGET — idiomatic Go, `(int, error)` |
| `corpus/` | compound/single units, repeated units, zero, and two malformed inputs |
| `verify.sh` | differential proof: source reproduces golden **and** port matches |

## Run it

```sh
./verify.sh                          # equivalence proof
ruff check reference.py              # Python land-green
gofmt -l port.go; go vet port.go     # Go land-green
```

Status: **source and port agree on all 9 inputs; ruff + gofmt + go vet
clean.**

## Note on out-of-contract input

Extremely large numbers diverge (Python `int` is unbounded; Go `strconv.Atoi`
overflows), so the corpus stays within `int64`. A production port would
surface the Atoi error instead of ignoring it — called out here as a
documented boundary, per the skill's equivalence discipline.
