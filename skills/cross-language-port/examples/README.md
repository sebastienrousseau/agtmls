# cross-language-port — worked examples

Each example is a **runnable, verified** port: a `reference.<ext>` (source),
a `port.<ext>` (idiomatic target), a golden-I/O `corpus/`, and a `verify.sh`
that proves behavioural equivalence by running both and diffing. Every
example is chosen from a real fleet domain and teaches a specific landmine
from `../reference.md`.

Run them all:

```sh
for v in */verify.sh; do echo "== $v =="; "$v"; done
```

## Roster

| Example | Direction | Fleet domain | Landmine taught | Status |
|---|---|---|---|---|
| [`py-to-rust-iban`](py-to-rust-iban/) | Python → Rust | banking (`pain001`, `camt053`) | integer width: bignum `% 97` → incremental mod (u128 overflow) | ✅ 8/8, tests pass |
| [`bash-to-python-pathdedupe`](bash-to-python-pathdedupe/) | Bash → Python | dotfiles / shell tooling | word-splitting + glob expansion of unquoted `$var` | ✅ 8/8, glob-safe |

## Planned (Phase 1 remaining — see the skill's 10/10 plan)

| Example | Direction | Landmine to teach |
|---|---|---|
| `js-to-ts-*` | JavaScript → TypeScript | runtime type erasure → validate at the boundary (`zod`) |
| `go-to-rust-*` | Go → Rust | `(T, error)` + zero values → `Result` + `Option` |
| `rust-to-swift-*` | Rust → Swift | `enum` associated values → `throws` vs `Result` convention |
| `py-to-go-*` | Python → Go | exceptions → `if err != nil`, no sum types |

## How each example is validated

1. `corpus/expected.txt` is generated **by the source** — it is the source's
   real output, not a hand-written guess.
2. `verify.sh` first confirms the source still reproduces the golden (guards
   against the reference drifting), then runs the port against the same
   corpus and diffs. Any mismatch exits non-zero.
3. Both files pass their language's formatter + linter + tests ("land green"
   — `../reference.md` §R1.1).

This is the differential golden-I/O method from `../reference.md` §R3.1,
made executable — the same discipline noyalib uses to catch cross-path
divergences a pile of unit tests would miss.
