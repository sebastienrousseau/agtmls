# harness/ — reusable equivalence tooling

Turns the differential golden-I/O method (`../reference.md` §R3) into shared,
runnable tooling, so every worked example — and every real port you do —
proves equivalence the same way instead of re-implementing the diff loop.

## `golden-diff.sh` — the runner

Given a corpus, a golden output, and two runnable commands (source, port),
it proves **(1)** the source still reproduces the golden and **(2)** the port
matches it, printing a unified diff and exiting non-zero on any mismatch.
Every example's `verify.sh` is now a thin wrapper: build the target if it's
compiled, then one call.

```sh
golden-diff.sh <input> <golden> <source-cmd> <port-cmd>
```

```sh
# from an example's verify.sh, after compiling the target to $bin:
../../harness/golden-diff.sh corpus/input.txt corpus/expected.txt \
    "python3 reference.py" "$bin"
```

### Add a new example

1. Write `reference.<ext>` (source) and `port.<ext>` (idiomatic target).
2. `corpus/input.txt` — representative inputs, **including edge cases**.
3. Generate the golden **from the source** (never hand-write it):
   `<run source> < corpus/input.txt > corpus/expected.txt`.
4. `verify.sh` — build (if compiled), then call `golden-diff.sh`.

## `port-check.sh` — the land-green gate

`golden-diff.sh` proves *equivalence*; `port-check.sh` proves the port is
*clean* — it runs the target language's formatter (check mode), linter /
typecheck, and a compile-or-syntax gate. A port is not done until this is
GREEN (execution-loop Phase 6).

```sh
port-check.sh <lang> <path...>   # lang: rust|python|go|cpp|swift|ts|js|ruby|bash
```

Tools that are installed run; missing ones (e.g. `prettier`, `tsc`,
`rubocop`, `clang-format`, `swift-format` on a bare box) report **SKIP**, not
FAIL, so the gate is usable anywhere. It exits non-zero only if a *present*
tool reports a problem. Every worked example's `port.<ext>` passes it.

## `templates/` — differential property tests

For pure functions a property test beats a fixed corpus: generate random
inputs and assert `port(x) == reference(x)`, using the source as an oracle.
One template per generator ecosystem — wire in your function's input domain
and the two commands, then run. See `../reference.md` §R3.2.

| Template | Ecosystem | Oracle |
|---|---|---|
| `templates/hypothesis_diff.py` | Python `hypothesis` | source binary via subprocess |
| `templates/proptest_diff.rs` | Rust `proptest` | source binary via subprocess |
| `templates/fast-check_diff.mjs` | JS/TS `fast-check` | source binary via subprocess |

Why an oracle beats hand-written cases: a single differential property finds
the edge you didn't think of — the same reason noyalib's cross-path fuzz
target caught a silent divergence 4000 unit tests missed.
