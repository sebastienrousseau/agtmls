# Language profile: Rust

You are working in a Rust project. The universal rules above still
apply; this section refines them for Rust idioms.

## Error handling

- Library boundaries: return `Result<T, YourError>` with a real
  error type. Use `thiserror` for library errors; reserve `anyhow`
  for binaries (`main.rs`, integration glue) where the caller has
  no reason to match on variants.
- Never surface `Box<dyn Error>` from a library — it forces every
  caller into stringly-typed handling.
- Errors that "cannot happen" are still a `Result::Err(variant)`
  when the input is external. Reserve `unreachable!()` and
  `unwrap_or_else(|_| unreachable!())` for genuine invariant
  violations proved by construction, and prefer a dedicated
  `Error::InvariantViolated(&'static str)` variant so bug reports
  survive optimized builds.
- Use `?` over `match err`, and `.map_err(Error::from)` at the
  boundary where a foreign error is adapted to your own type.
- Propagate spans / positions on parse errors when the domain has
  them — a source location is worth ten error messages.

## `unsafe` policy

- Default: `#![forbid(unsafe_code)]` at every crate root. `forbid`
  (not `deny`) is deliberate — `#[allow(unsafe_code)]` cannot
  locally re-enable it.
- If a project genuinely needs `unsafe`, contain it behind a small
  audited module, and every `unsafe` block carries a `// SAFETY:`
  comment explaining the invariants the caller must uphold.
- Prefer vetted crates over hand-rolled unsafe:
  `memchr` / `bytecount` / `simdutf8` for byte scanning,
  `smallvec` / `bytes` for buffers, `arrayvec` for stack vectors.
  Adding a `unsafe`-using crate is a supply-chain decision — justify
  it in the PR.

## Public API surface

- Every public item carries rustdoc:
  - One-line summary.
  - `# Examples` block with a runnable doctest. Doctests are
    load-bearing tests — treat them as such.
  - `# Errors` section on any fallible function enumerating the
    error variants a caller may see.
  - `# Panics` section on any function that can panic and isn't a
    genuine invariant violation.
- Public config structs and error enums carry `#[non_exhaustive]`
  so adding a field or variant is not a breaking change.
- `impl Trait` in argument position; concrete or `impl Trait`
  return types depending on whether the caller needs to name it.
- Public functions returning `Result` carry `#[must_use]`.
- Newtypes for domain values (e.g. `struct UserId(u64)`) rather
  than shipping bare integers through half a library.

## Types and idioms

- API inputs: `&str`, `&[T]`, `impl AsRef<Path>`, `impl Into<T>` —
  accept broadly.
- API outputs: owned (`String`, `Vec<T>`, `PathBuf`) unless
  lifetime-tied borrows are actually cheaper.
- `Cow<'a, str>` when a function returns the input unchanged in the
  common case and only allocates on the rare transformation.
- Iterator combinators over explicit `for` loops when the resulting
  expression is clearer, not shorter for its own sake.
- Prefer `matches!` for boolean-shaped enum tests.
- `Option::and_then` / `Result::and_then` before nested `match` for
  chained fallibility.
- Don't clone in a hot path to satisfy the borrow checker without
  measuring the alternative first.

## Testing discipline

- `#[cfg(test)] mod tests` for unit tests colocated with source.
- `tests/*.rs` for integration tests.
- Doctests count as tests; they must run under `cargo test` and
  must assert semantics, not just compile.
- Cross-path parity: if two code paths (e.g. streaming vs
  in-memory, sync vs async, Value vs typed target) claim the same
  semantics, a test that runs both against a shared corpus and
  compares outputs is mandatory. "Wrong-but-green" (both agree on
  the wrong answer) is caught by fuzz differential targets, not by
  unit tests.
- Regression test discipline: fix a bug by first writing a test
  that fails on the pre-fix tree, then landing both in the same
  commit.
- Property tests (`proptest` / `quickcheck`) for combinatorial
  input spaces (escape sequences, integer boundaries, Unicode
  categories).
- Criterion benches for performance claims. A perf claim without a
  reproducible bench in the same PR is unsubstantiated.

## Cargo hygiene

- `rust-version` in `Cargo.toml` is the MSRV floor. Bumping it is a
  breaking change — treat MSRV bumps as a minor-version (pre-1.0:
  patch) event with an ADR if the project has one.
- Features are additive-only. A feature that changes the behaviour
  of code that doesn't opt into it is a bug.
- No `git = "..."` deps in a crate that will be published — crates.io
  refuses them. Vendored deps or a workspace path is fine locally.
- Prefer workspace-level `[lints]` tables so lint policy lives in
  one place rather than every crate root.
- No `[patch.crates-io]` unless the reason is documented alongside
  it and the patch is time-boxed.

## Toolchain

- `cargo fmt` clean before every push. `rustfmt.toml` is checked in
  and edition-locked.
- `cargo clippy --all-targets --all-features -- -D warnings` clean.
  A clippy lint you disagree with gets an `#[allow(...)]` with a
  comment explaining why, or a workspace-wide `[lints.clippy]`
  override with the same justification.
- `edition = "..."` matches the MSRV floor and is set explicitly.
- `#[deny(missing_docs)]` at the crate root for public libraries.

## What NOT to do

- No Python-style class hierarchies. Use traits, generics, and
  composition.
- No JS-style dynamic dispatch as the default. `dyn Trait` is a
  tool for erasure at API boundaries, not a habit.
- No blanket `.clone()` to escape lifetimes without profiling.
- No `unwrap()` / `expect()` in library code without a comment
  explaining the invariant that makes it safe.
- No `println!` / `eprintln!` inside a library. Use the `log` or
  `tracing` facade so the caller decides what's visible.
