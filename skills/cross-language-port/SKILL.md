---
name: cross-language-port
description: >-
  Autonomously port a module, script, CLI, or function from one language to
  another across the polyglot fleet — Rust, Python, Go, C++, Swift,
  TypeScript, JavaScript, Ruby, and Bash/Shell — preserving business logic
  exactly while adopting the target language's idioms, error model,
  concurrency shape, and toolchain, AND proving behavioural equivalence with
  a differential golden-I/O harness rather than eyeballing. Load when the
  user says "port this to <lang>", "translate to <lang>", "rewrite in
  <lang>", "convert this to <lang>", "reimplement <X> in <lang>", "give me
  the <lang> equivalent", or asks for a Rust↔Python↔Go↔Swift↔TS/JS↔Ruby↔C++
  ↔Bash equivalent of existing code. Not for micro-snippets (do those
  inline) or behaviour-changing redesigns (that's a rewrite, clarify intent
  first).
---

# Skill: cross-language porting

**Trigger.** The user asks to *port this*, *translate to [Language]*,
*rewrite in [Language]*, *convert this to [Language]*, *reimplement X in
[Language]*, or *give me the [Language] equivalent*.

> **Reference material** (the full cross-language idiom-mapping matrix,
> per-language porting notes + landmines, the equivalence-harness recipes,
> and the data-boundary/FFI contracts): see `reference.md` in this
> directory. This file is the doctrine + the execution loop; `reference.md`
> is the lookup and the recipes.

## Objective

Port a specific module, script, CLI, or function from a **source** language
to a **target** language so that:

1. **Behaviour is preserved exactly** — same inputs produce same outputs,
   same errors, same side-effect ordering. This is proven, not asserted
   (see §4).
2. **The output is idiomatic** — it reads as if a senior engineer *native
   to the target language* wrote it from the spec, not transliterated
   line-for-line from the source.
3. **It lands green** — formatted, linted, and tested with the target
   language's own toolchain before you call it done.

## Supported languages (the fleet)

Every one is a first-class **source and target**. Anchor per language —
full toolchain rows (formatter / linter / test runner / package manager /
error model / async model / HTTP / JSON) are in `reference.md` §R1.

| Language | Idiom anchor | Format · Lint · Test |
|---|---|---|
| **Rust** | ownership, `Result<T,E>` + `?`, traits over inheritance | rustfmt · clippy -D warnings · `cargo test` |
| **Python** | duck typing, EAFP, type hints + `mypy`, context managers | ruff format · ruff + mypy · pytest |
| **Go** | `(T, error)` returns, goroutines + channels, small interfaces | gofmt · go vet + golangci-lint · `go test` |
| **C++** | RAII, `std::expected`/exceptions, smart pointers, no raw `new` | clang-format · clang-tidy · GoogleTest/Catch2 |
| **Swift** | `throws`/`Result`, `async/await` + actors, value types, `Codable` | swift-format · SwiftLint · swift-testing/XCTest |
| **TypeScript** | discriminated unions, `strict` mode, `async/await`, no `any` | prettier · eslint + `tsc --noEmit` · vitest |
| **JavaScript** | `async/await`, modules, immutability by default | prettier · eslint · vitest/node:test |
| **Ruby** | blocks/enumerables, `raise`/`rescue`, duck typing | rubocop -a · rubocop · RSpec/minitest |
| **Bash/Shell** | `set -euo pipefail`, exit codes, pipes, `trap` | shfmt · shellcheck · bats |

Do not invent a target outside this set without confirming it exists in the
fleet (`github.com/sebastienrousseau`). If the user names one that isn't
here, port it anyway but say the target is outside the standard fleet.

## Execution plan

Six phases. Do not skip §4 — it is what separates a port from a guess.

1. **Scope & contract.** Read the source in full. Write down, in prose, the
   *observable contract*: inputs (types, ranges, encodings), outputs, error
   conditions, side effects and their ordering, and any concurrency. This
   contract — not the source lines — is what you port. If the contract is
   ambiguous, that ambiguity is the first thing to resolve.

2. **Source analysis.** Identify the core algorithm, external dependencies
   (I/O, network, filesystem, env), edge-case handling, and the concurrency
   model. Flag anything source-language-specific that has no direct target
   analogue (GIL assumptions, Go's zero values, Rust lifetimes, Ruby
   monkey-patching, Bash word-splitting) — these are the porting risks.

3. **Idiom mapping.** Map each construct to its *idiomatic* target
   equivalent, not its literal one. Use the matrix in `reference.md` §R1.
   The load-bearing axes:
   - **Error model** — source exceptions → target's `Result`/`error`/
     `throws`/exit-code convention. Never smuggle try/except into Rust or
     `if err != nil` into Python.
   - **Concurrency** — `asyncio.gather`↔`Promise.all`↔`tokio::join!`↔
     goroutines+`WaitGroup`↔Swift `TaskGroup`↔Ruby threads↔`std::async`↔
     Bash `&`+`wait`.
   - **Collections & iteration** — comprehensions ↔ iterator combinators ↔
     range-for ↔ enumerables ↔ streams. Prefer the target's expression
     form when it's clearer, not shorter for its own sake.
   - **Data boundaries** — see §3 boundary rules.

4. **Translate.** Write the target code from the *contract*, in the target's
   idiom. Rules:
   - **Not a 1:1 line translation.** Restructure so it reads native.
   - **Adopt the target error model fully.**
   - **Use vetted standard libraries**, named in `reference.md` §R1/§R2
     (e.g. Python `requests`→Rust `reqwest`, C++ `std::thread`→Go
     goroutines, JS `Promise.all`→Python `asyncio.gather`).
   - **Respect the target's memory/ownership model** — RAII in C++, borrow
     discipline in Rust, ARC in Swift; do not paper over it with clones or
     `unsafe`/`any`.

5. **Prove behavioural equivalence (the load-bearing phase).** Build a
   **golden-I/O corpus** from the *source* — representative inputs paired
   with the source's actual outputs — then run the port against the same
   corpus and diff. Any divergence is a port bug until explained. For pure
   functions, add a property test asserting `port(x) == reference(x)` over
   generated inputs. The full differential-harness recipe (per language
   pair) is in `reference.md` §R3. "It compiles and looks right" is **not**
   equivalence.

6. **Land it green.** Format, lint, and test with the *target's* toolchain
   (table above; commands in `reference.md` §R1) until all three pass.
   Deliver the ported file(s) + the equivalence tests + the golden corpus.

## Data-boundary & interop rules

When the port keeps a foot in both languages (a Python service shelling out
to a new Rust binary, a Go caller of a C++ FFI shim, a TS frontend hitting a
new Ruby endpoint), enforce a **structured contract at the boundary** —
JSON, Protocol Buffers, or a strict CLI stdout/exit-code contract. Never
ad-hoc string-parse across a language boundary. Boundary specifics
(serialization parity, integer-width and float-format traps, error
propagation across the seam) are in `reference.md` §R4.

## Safety at the port boundary

- **Secrets never move into source.** If the original read a key from env or
  a vault, the port does too — don't inline a value you found in a fixture.
- **Re-validate all input in the target.** A port is a fresh attack surface;
  the source's validation assumptions may not survive the idiom change
  (Bash word-splitting → argv, Python `int` bignum → Rust `i64` overflow,
  JS number precision → other languages' integer types).
- **No new `unsafe` (Rust) / `any` (TS) / raw `new` (C++) / `eval`** to
  force a shortcut. If the idiomatic path needs one, that's a design
  question to surface, not a silent choice.

## Worked examples

Runnable, verified ports live in `examples/` — each a `reference.<ext>`
(source) + `port.<ext>` (idiomatic target) + golden `corpus/` + `verify.sh`
that proves equivalence. Study the one closest to your port before starting;
copy its shape. Roster (`examples/README.md` indexes them), each teaching a
distinct landmine:

- **`py-to-rust-iban/`** — Python → Rust; integer width (bignum `% 97` →
  incremental mod, because the value overflows `u128`).
- **`bash-to-python-pathdedupe/`** — Bash → Python; word-splitting + glob
  expansion of unquoted `$var` (a `/tmp/*` segment must stay literal).
- **`js-to-ts-configvalidate/`** — JavaScript → TypeScript; runtime type
  erasure (validate `unknown` at the boundary; a type cast validates
  nothing).
- **`go-to-rust-fraction/`** — Go → Rust; `(T, error)` + zero values →
  `Result` + `?`, and matching Go's split semantics exactly.
- **`rust-to-swift-op/`** — Rust → Swift; `enum` associated values map 1:1,
  but `Result` → `throws` (adopt the target's error channel).
- **`py-to-go-duration/`** — Python → Go; exceptions → `if err != nil`, no
  sum types (control flow inverts from throw/catch to return/check).
- **`py-to-cpp-hexcolor/`** — Python → C++; exceptions → `std::expected`
  (C++23) and RAII (no `new`/`delete`).
- **`ruby-to-python-histogram/`** — Ruby → Python; Enumerable/`tally`/blocks
  → `Counter` + comprehensions (watch the codepoint sort order).

Eight directions covering all nine fleet languages. Every `verify.sh` is a
thin wrapper over the shared runner in `harness/` (`golden-diff.sh` +
differential property-test templates). Run every proof at once:

```sh
for v in examples/*/verify.sh; do "$v"; done
```

## When NOT to use this skill

- **Micro-porting** (a single function of a few lines) — do it inline in the
  conversation without invoking this skill.
- **Behaviour-changing rewrites** — that's a redesign, not a port. Clarify
  the intended new behaviour with the user first; the equivalence harness in
  §5 assumes the contract is *preserved*.
- **Porting *within* a language** (2→3, ES5→ESNext, C++17→23) — that's a
  migration/modernization, not a cross-language port.

## Provenance & maintenance

- Fleet languages are derived from the active repos at
  `github.com/sebastienrousseau` (Rust, Python, Go, C++, Swift, TypeScript,
  JavaScript, Ruby, Shell). Re-derive with:
  `gh api 'users/sebastienrousseau/repos?per_page=100&type=owner' --jq '.[]|select(.fork==false)|.language' | sort | uniq -c | sort -rn`
- Toolchain rows in `reference.md` §R1 name current-stable tools; re-verify
  a formatter/linter/test-runner exists before scripting it into a port.
- Last reviewed against the fleet: 2026-07-08.
