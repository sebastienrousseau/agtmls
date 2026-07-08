# Worked port — Rust → Swift: op evaluator over an enum

Fleet domain: Rust (`qrc`, `vrd`) → Swift (`AudioWaveLib`, `WiserOneApp`).

## What this teaches

**Enum associated values + error-channel convention (`reference.md` §R2
Swift, §R1.2).** Rust's `enum Op { Add(i64,i64), Neg(i64) }` maps almost
1:1 to Swift's `enum Op { case add(Int,Int); case neg(Int) }` — Swift has
associated values too, so the data model is a near-transliteration. What
must change is the **error channel**: Rust's `Result<T, String>` (which the
caller `match`es) becomes Swift's native `throws` (which the caller drives
with `try` / `do-catch`). Keeping `Result` in Swift would compile but read
as non-native; adopting `throws` is the whole point.

`match` on the enum → Swift `switch` with `case let` binding; Rust
`str::parse` → Swift `Int(_:)` returning an optional, guarded with `guard`.

## Files

| File | Role |
|---|---|
| `reference.rs` | SOURCE — idiomatic Rust, `enum` + `Result` |
| `port.swift` | TARGET — idiomatic Swift, `enum` + `throws` |
| `corpus/` | valid ops, unknown op, wrong arity, non-integer operand |
| `verify.sh` | differential proof: source reproduces golden **and** port matches |

## Run it

```sh
./verify.sh                 # equivalence proof (compiles Rust, interprets Swift)
swift-format lint port.swift   # Swift land-green (needs swift-format)
```

Status: **source and port agree on all 8 inputs.**
