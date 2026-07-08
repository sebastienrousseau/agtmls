# Boundary traps — runnable seam tests

When a port leaves a **live seam** between two languages (a service shelling
out to a new binary, a frontend hitting a new backend, JSON crossing a
process boundary), the seam has failure modes the within-language equivalence
proof never sees. These are runnable demonstrations that a trap **bites** and
that the documented contract **catches** it — the executable form of
`../../reference.md` §R4.

Run them all:

```sh
for v in */verify.sh; do echo "== $v =="; "$v"; done
```

## Traps

| Trap | Demonstrates | Status |
|---|---|---|
| [`integer-width/`](integer-width/) | a `u64` above 2^53 loses precision as a JSON **number** (JS/JSON numbers are f64) but survives as a JSON **string** — the exact trap noyalib's `lossless-u64` defeats | ✅ runnable: trap bites + string contract holds |

Each `verify.sh` exits non-zero unless it observes **both** the trap firing
*and* the contract preventing it — so it fails loudly if a runtime ever
"fixes" the trap (which would mean the contract is being tested against a
false premise).

## Other §R4 seam traps to script next

Documented in `../../reference.md` §R4; not yet packaged as runnable demos:

- **Encoding** — UTF-8 vs a locale-default encoding corrupting bytes across a
  C++/Bash seam.
- **Error propagation** — a failure on the far side of a CLI seam must surface
  as a non-zero exit code + stderr, never vanish into the near side's success
  path. (The worked examples already model the exit-code contract within one
  process; the seam version crosses two.)
