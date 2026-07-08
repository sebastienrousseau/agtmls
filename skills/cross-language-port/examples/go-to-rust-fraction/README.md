# Worked port — Go → Rust: reduce a fraction

Fleet domain: Go tooling (`corral`, `corral-sync`) → Rust.

## What this teaches

**The error-model + zero-value idiom shift (`reference.md` §R2 Go/Rust,
§R1.2).** Go returns `(T, error)`; on failure the value slot holds the
zero value and the caller branches on `err != nil`. Rust replaces this with
`Result<T, E>` — no zero-value ambiguity, and the compiler *forces* the
caller to handle the error. Go's `strconv.Atoi` (value, error) becomes
`str::parse` returning a `Result`, threaded with `?`; the imperative
`if err != nil` ladders collapse into `?` + `match`.

**The subtle equivalence trap it catches:** Go's `strings.Split("1/2/3","/")`
yields 3 parts → rejected as "expected a/b". A naive Rust port with
`split_once('/')` would instead read `1` and `"2/3"` and fail differently.
The port matches Go's splitting semantics exactly — the golden corpus has
`1/2/3` specifically to pin this.

## Files

| File | Role |
|---|---|
| `reference.go` | SOURCE — idiomatic Go, `(string, error)` |
| `port.rs` | TARGET — idiomatic Rust, `Result<String, &str>` + `?` |
| `corpus/` | reductions, sign normalization, div-by-zero, non-integer, arity |
| `verify.sh` | differential proof: source reproduces golden **and** port matches |

## Run it

```sh
./verify.sh                                          # equivalence proof
gofmt -l reference.go; go vet reference.go           # Go land-green
rustc --edition 2021 --test port.rs -o /tmp/t && /tmp/t   # Rust unit tests
```

Status: **source and port agree on all 9 inputs; 2 Rust unit tests pass;
gofmt + go vet clean.**
