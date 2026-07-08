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

## Roster — one verified port per family, all nine fleet languages

| Example | Direction | Fleet domain | Landmine taught | Status |
|---|---|---|---|---|
| [`py-to-rust-iban`](py-to-rust-iban/) | Python → Rust | banking (`pain001`, `camt053`) | integer width: bignum `% 97` → incremental mod (u128 overflow) | ✅ 8/8, tests pass |
| [`bash-to-python-pathdedupe`](bash-to-python-pathdedupe/) | Bash → Python | dotfiles / shell tooling | word-splitting + glob expansion of unquoted `$var` | ✅ 8/8, glob-safe |
| [`js-to-ts-configvalidate`](js-to-ts-configvalidate/) | JavaScript → TypeScript | JS/TS tooling (`crypto-service`) | runtime type erasure → validate `unknown` at the boundary | ✅ 8/8 |
| [`go-to-rust-fraction`](go-to-rust-fraction/) | Go → Rust | Go tooling (`corral`) | `(T, error)` + zero values → `Result` + `?` | ✅ 9/9, tests pass |
| [`rust-to-swift-op`](rust-to-swift-op/) | Rust → Swift | Rust (`qrc`) → Swift (`AudioWaveLib`) | `enum` associated values → `throws` vs `Result` | ✅ 8/8 |
| [`py-to-go-duration`](py-to-go-duration/) | Python → Go | Python services → Go | exceptions → `if err != nil`, no sum types | ✅ 9/9 |
| [`py-to-cpp-hexcolor`](py-to-cpp-hexcolor/) | Python → C++ | `euxis` | exceptions → `std::expected` (C++23) + RAII | ✅ 8/8 |
| [`ruby-to-python-histogram`](ruby-to-python-histogram/) | Ruby → Python | `homebrew-tap` | Enumerable/`tally`/blocks → `Counter`; codepoint sort order | ✅ 3/3 |

Eight directions covering **all nine** fleet languages as source and/or
target: Rust, Python, Go, C++, Swift, TypeScript, JavaScript, Ruby, Bash.
Each teaches a distinct landmine from `../reference.md`.

Every `verify.sh` is a thin wrapper over the shared runner in
[`../harness/`](../harness/) — build the target if compiled, then one
`golden-diff.sh` call.

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
