# Worked port — Python → Rust: IBAN mod-97 validation

Fleet domain: payments/banking (`pain001`, `camt053`, `bankstatementparser`).

## What this teaches

**The integer-width landmine (`reference.md` §R4).** The idiomatic Python
builds the entire rearranged IBAN as one arbitrary-precision `int` and takes
`% 97`. Python `int` has no width limit, so this is correct *and* idiomatic.

A **1:1 transliteration into Rust would overflow**: the expanded IBAN reaches
~40 decimal digits, past even `u128` (~39). The idiomatic Rust port never
builds the big number — it **folds the remainder incrementally**
(`rem = (rem*10 + d) % 97`), so `u32` is always enough. Same contract, same
outputs, but the port is restructured around the target's constraints rather
than copied line-for-line. That is the whole point of the skill.

Secondary idiom shifts: Python `bool` return → same; Python EAFP/`str`
methods → Rust byte inspection; Python `.replace(" ", "")` (only U+0020) is
matched exactly by Rust `filter(|&c| c != ' ')` — *not* `is_whitespace()`,
which would diverge on tabs (a real equivalence trap).

## Files

| File | Role |
|---|---|
| `reference.py` | SOURCE — idiomatic Python (bignum mod-97) |
| `port.rs` | TARGET — idiomatic Rust (incremental mod-97) |
| `corpus/input.txt` | representative inputs (valid, invalid, spaced, lowercase, wrong-length) |
| `corpus/expected.txt` | golden output, produced by the SOURCE |
| `verify.sh` | differential proof: source reproduces golden **and** port matches it |

## Run it

```sh
./verify.sh                              # equivalence proof (source vs port)
rustc --edition 2021 --test port.rs -o /tmp/t && /tmp/t   # Rust unit tests
ruff check reference.py                  # Python land-green
```

`verify.sh` exits non-zero on any divergence. Current status: **source and
port agree on all corpus inputs; 3 Rust unit tests pass.**

## Contract

One IBAN per stdin line; each non-empty line prints `valid` or `invalid`.
ASCII input; only the space character is stripped. Unicode normalization is
intentionally out of contract — see the equivalence trap above.
