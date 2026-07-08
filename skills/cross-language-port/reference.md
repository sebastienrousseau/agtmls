# cross-language-port — reference material

Complements `SKILL.md` in this directory. Load when the doctrine + loop in
`SKILL.md` aren't enough — you need the full idiom-mapping matrix, the
per-language porting notes and landmines, an equivalence-harness recipe, or
the data-boundary contracts.

Fleet: **Rust, Python, Go, C++, Swift, TypeScript, JavaScript, Ruby,
Bash/Shell** (derived from `github.com/sebastienrousseau`). Tool names are
current-stable as of 2026-07-08 — re-verify a tool exists before scripting
it into a port.

---

## R1. Idiom-mapping matrix

### R1.1 Toolchain per language

| Language | Package/build | Formatter | Linter / typecheck | Test runner |
|---|---|---|---|---|
| Rust | `cargo` | `rustfmt` | `clippy -D warnings` | `cargo test` (+ doctests) |
| Python | `uv` / `poetry` / `pip` | `ruff format` (or `black`) | `ruff` + `mypy` | `pytest` |
| Go | `go mod` | `gofmt` / `goimports` | `go vet` + `golangci-lint` | `go test ./...` |
| C++ | CMake + `vcpkg`/Conan | `clang-format` | `clang-tidy` | GoogleTest / Catch2 / `ctest` |
| Swift | SwiftPM | `swift-format` | `SwiftLint` | `swift test` (swift-testing/XCTest) |
| TypeScript | `pnpm`/`npm` | `prettier` | `eslint` + `tsc --noEmit` | `vitest` |
| JavaScript | `pnpm`/`npm` | `prettier` | `eslint` | `vitest` / `node --test` |
| Ruby | Bundler + `gem` | `rubocop -a` / `standardrb` | `rubocop` + `sorbet`(opt) | RSpec / minitest |
| Bash/Shell | n/a | `shfmt` | `shellcheck` | `bats` |

### R1.2 Error model

| Language | Idiomatic error handling | Anti-pattern to avoid |
|---|---|---|
| Rust | `Result<T, E>` + `?`; `thiserror` (lib) / `anyhow` (bin) | `unwrap()` in library code; `panic!` for recoverable errors |
| Python | raise/`except`; custom exception classes; EAFP | returning `None`/`-1` sentinels; bare `except:` |
| Go | `(T, error)`; `if err != nil`; `errors.Is/As`; wrap with `%w` | panics for expected failures; ignoring `err` |
| C++ | exceptions or `std::expected<T,E>` (C++23); RAII cleanup | error codes silently ignored; leaks on the throw path |
| Swift | `throws` + `try`/`do-catch`; `Result`; typed errors | force-`try!`; `fatalError` on recoverable input |
| TypeScript | `throw` + `try/catch`; discriminated-union `Result`; never `any` for errors | swallowing in empty `catch {}`; `throw "string"` |
| JavaScript | `throw`/`try-catch`; `Error` subclasses; reject Promises | throwing non-`Error` values; unhandled rejections |
| Ruby | `raise`/`rescue`; custom `StandardError` subclasses | `rescue => e` catching everything; `rescue nil` |
| Bash | `set -euo pipefail`; exit codes; `trap … ERR/EXIT` | unchecked commands; parsing `$?` after a pipe without `pipefail` |

### R1.3 Concurrency & async (the same job, nine shapes)

"Run N tasks concurrently, wait for all":

| Language | Idiom |
|---|---|
| Rust | `tokio::join!` / `futures::future::join_all` / threads + `JoinHandle` |
| Python | `await asyncio.gather(*tasks)` |
| Go | `go f()` per task + `sync.WaitGroup` (or `errgroup.Group`) |
| C++ | `std::async` + `future.get()`, or `std::jthread` + join |
| Swift | `async let` / `withTaskGroup`; actors for shared state |
| TypeScript/JS | `await Promise.all(tasks)` |
| Ruby | `Thread.new` + `join`; or the `async` gem / `Ractor` |
| Bash | `cmd &` per task + `wait` (capture PIDs for per-task status) |

Shared-state discipline differs: Rust `Arc<Mutex<_>>`, Go channels ("share
memory by communicating"), Swift actors, Python asyncio single-thread +
locks for threads, JS single-threaded event loop (no data races, but
interleaving), C++ `std::mutex`, Ruby GVL (threads interleave; use `Mutex`).

### R1.4 Common library equivalents

| Task | Rust | Python | Go | Swift | TS/JS | Ruby | C++ |
|---|---|---|---|---|---|---|---|
| HTTP client | `reqwest` | `httpx`/`requests` | `net/http` | `URLSession` | `fetch`/`axios` | `Net::HTTP`/`faraday` | `libcurl`/`cpp-httplib` |
| JSON | `serde_json` | `json`/`pydantic` | `encoding/json` | `Codable` | `JSON`/`zod` | `json` | `nlohmann/json` |
| CLI args | `clap` | `argparse`/`click` | `flag`/`cobra` | `ArgumentParser` | `commander`/`yargs` | `optparse`/`thor` | `CLI11` |
| Datetime | `chrono`/`time` | `datetime`/`arrow` | `time` | `Foundation.Date` | `Temporal`/`date-fns` | `Time`/`date` | `<chrono>` |
| Regex | `regex` | `re` | `regexp` | `NSRegularExpression`/`Regex` | native `RegExp` | native `Regexp` | `<regex>`/RE2 |
| Logging | `tracing`/`log` | `logging`/`structlog` | `log/slog` | `os.Logger` | `pino`/`winston` | `Logger` | `spdlog` |

---

## R2. Per-language porting notes & landmines

### Rust (as target)
- Adopt: `Result`+`?`, iterator combinators, `match`, newtypes, `#[derive]`.
- Avoid: `.clone()` to escape the borrow checker without measuring;
  `unwrap()` in library paths; `unsafe` (the fleet forbids it — see the Rust
  system profile). Model nullability with `Option<T>`, not sentinels.
- Landmine (from Python/JS): integers are fixed-width. A Python bignum or a
  JS `number` can silently overflow `i64`/`u64` — pick the width from the
  contract and test the boundary.

### Python (as target)
- Adopt: type hints + `mypy`, dataclasses/pydantic, context managers
  (`with`), comprehensions, EAFP (`try` over `look-before-you-leap`).
- Avoid: re-creating Go's `if err != nil` with tuple returns; C++-style
  getter/setter classes; manual resource close instead of `with`.
- Landmine (from Rust/Go): no compile-time types — the `mypy` pass **is**
  the typecheck; a port without it loses a guarantee the source had.

### Go (as target)
- Adopt: `(T, error)`, small interfaces defined at the consumer, goroutines
  + channels, zero-value-usable structs, `defer` for cleanup.
- Avoid: exceptions-as-panics; deep inheritance (Go has none — use
  composition + interfaces); generics where an interface is clearer.
- Landmine (from Rust/Swift): no sum types. A Rust `enum` with data becomes
  an interface + concrete types, or a tagged struct — pick one and be
  consistent; don't fake it with `interface{}`.

### C++ (as target)
- Adopt: RAII everywhere, smart pointers (`unique_ptr`/`shared_ptr`, never
  raw `new`/`delete`), `std::expected`/`std::optional`, `const`-correctness,
  the rule of zero.
- Avoid: manual memory management; C-style casts; ignoring exception-safety
  on the throw path.
- Landmine (from GC languages): object lifetime is explicit. A Python/JS/Go
  object that "just lives" needs an owner and a defined lifetime in C++.

### Swift (as target)
- Adopt: value types (`struct`/`enum`) by default, `throws`/`Result`,
  `async/await` + actors, `Codable`, optionals over sentinels, protocol-
  oriented design.
- Avoid: force-unwrap `!` and `try!` on real input; reference types where a
  value type fits; `fatalError` for recoverable cases.
- Landmine (from Rust): Swift `enum`s carry associated values like Rust's,
  but error handling is `throws`, not `Result` by default — match the
  surrounding code's convention.

### TypeScript (as target)
- Adopt: `strict` tsconfig, discriminated unions for variants, `unknown`
  over `any`, `readonly`, exhaustive `switch` with `never` checks.
- Avoid: `any`; non-null `!` assertions to silence the checker; classes
  where a function + type suffices.
- Landmine (from typed languages): types are erased at runtime — validate
  external input with a runtime schema (`zod`) at the boundary; the compiler
  doesn't guard I/O.

### JavaScript (as target)
- Adopt: `async/await`, ES modules, `const`/immutability, `Array` methods
  over manual loops, `Error` subclasses.
- Avoid: callback pyramids; `var`; `==` (use `===`); floating-point money.
- Landmine: no static types at all — the golden-I/O harness (§R3) is doing
  double duty as your only correctness net; lean on it harder.

### Ruby (as target)
- Adopt: blocks + `Enumerable`, `raise`/`rescue` with typed errors, duck
  typing, keyword args, `frozen_string_literal`.
- Avoid: Java-style class ceremony; `rescue` without a class; mutating
  shared globals.
- Landmine (from static langs): method dispatch is dynamic and monkey-
  patchable — keep the port's surface small and test behaviour, not
  structure.

### Bash/Shell (as target — usually the *source*)
- Adopt: `set -euo pipefail`, `trap` for cleanup, `[[ ]]` over `[ ]`,
  quoted expansions `"$var"`, functions + exit codes, `local`.
- Avoid: unquoted expansions (word-splitting/globbing), parsing `ls`, `eval`
  on input, `$?`-after-pipe without `pipefail`.
- Landmine (porting *away* from Bash): word-splitting and exit-code
  semantics rarely have a clean analogue — porting Bash→Rust/Python usually
  means replacing implicit control flow (`set -e`) with explicit error
  handling. Porting *to* Bash is rarely idiomatic for anything non-trivial;
  push back if the logic wants real data structures.

---

## R3. Equivalence-verification recipes

The rule: **a port is proven equivalent by running both implementations
against the same inputs and diffing outputs** — never by inspection. Three
recipes, strongest first.

### R3.1 Golden-I/O corpus (the default)

1. Enumerate representative inputs for the source's contract — include edge
   cases (empty, max, malformed, unicode, boundary integers).
2. Capture the **source's** actual output for each (stdout, return value
   serialized to JSON, exit code, and error text if any). Commit as a
   `corpus/` of `input → expected` pairs.
3. Run the **port** against the same inputs; diff each output against the
   golden. Any mismatch is a port bug until you can explain it as an
   intended, documented difference.
4. Keep the corpus in the port's test suite so it stays true.

This is packaged as `harness/golden-diff.sh` — pass it the corpus, the
golden, and the two runnable commands; it proves the source still reproduces
the golden **and** the port matches it. Every worked example in `examples/`
uses it. See `harness/README.md`.

```sh
harness/golden-diff.sh corpus/input.txt corpus/expected.txt \
    "python3 reference.py" "$compiled_port_binary"
```

### R3.2 Differential property test (for pure functions)

When source and port can both be invoked from one harness (e.g. porting a
Python function to Rust, call the Python reference via subprocess), generate
random inputs and assert `port(x) == reference(x)`:

Starter templates live in `harness/templates/` (`proptest_diff.rs`,
`hypothesis_diff.py`, `fast-check_diff.mjs`) — wire in your input domain and
the two commands, then run.

- Rust: `proptest!` generating inputs, shelling to the reference.
- Python: `hypothesis` `@given` comparing to the ported binary.
- Go: `testing/quick`. TS/JS: `fast-check`. Swift: swift-testing + a
  generator. Ruby: `rantly`/PropCheck.

A single differential property replaces dozens of hand-written cases and
finds the edge you didn't think of. This mirrors how noyalib's
`fuzz_no_span_loader` caught a silent divergence 4000 unit tests missed.

### R3.3 Snapshot/round-trip (for serializers & formatters)

If the ported unit emits a format (JSON, YAML, CSV, a rendered template),
assert `parse(port_emit(x)) == x` and that `port_emit(x)` is byte-equal to
`source_emit(x)` on the corpus. Byte-equality is the strongest claim; if the
target's serializer orders keys differently, normalize both sides and say so.

### What does NOT count as equivalence

- "It compiles / typechecks." (necessary, not sufficient)
- "It looks right." (reading a diff is not running it)
- A test that calls the port and asserts nothing (wrong-but-green).
- Passing on one hand-picked happy-path input.

---

## R4. Data-boundary & FFI contracts

When the port leaves a live seam between two languages, the seam needs a
contract, not vibes.

- **Serialization parity.** Both sides agree on the wire format (JSON /
  protobuf / a fixed CLI contract). Test a round-trip across the seam, not
  just within each side.
- **Integer width & float format.** JSON numbers, Python bignums, JS
  `number` (f64), and Rust/Go/C++ fixed ints disagree at the edges. Pin the
  width in the contract; test `i64::MAX`, `2^53`, negative zero, `NaN`/`inf`
  handling explicitly. (noyalib's `lossless-u64` exists precisely because
  JSON/JS collapse `u64` into float — the same trap bites every port.)
- **Error propagation across the seam.** Decide how a failure on the far
  side surfaces: non-zero exit code + stderr for a CLI contract, an error
  field in the JSON envelope for a service. Never let one side's exception
  vanish into the other side's success path.
- **Encoding.** UTF-8 everywhere; declare it. Bash/C++ default encodings and
  locale settings are a classic silent corruptor across a seam.
- **Ordering & idempotence.** If the source guaranteed side-effect ordering
  (writes, log lines, callbacks), the port and the seam must preserve it —
  add it to the golden corpus as an observable.

---

## R5. Cross-references

- Doctrine, the six-phase loop, supported-language table, safety rules →
  `SKILL.md`.
- Universal engineering standards (structured data at boundaries, security-
  first, testing discipline) → the fleet system prompt (`_base.md`).
- Target-language house rules when the target is Rust → the Rust system
  profile (`system-prompts/rust.md`).
