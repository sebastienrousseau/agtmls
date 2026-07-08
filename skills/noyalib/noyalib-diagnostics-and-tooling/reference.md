# noyalib-diagnostics-and-tooling — extended reference

Complements `SKILL.md` (same directory). Date-stamp: 2026-07-08.

This file holds the inventories, output-format walkthroughs, and
full worked examples that would otherwise bloat the main SKILL
progressive-disclosure surface. Load it when you need the raw
inventory of what to measure or a byte-by-byte read of what a
tool prints.

Sections here mirror the SKILL.md order:

1. Coverage — TSV format walkthrough + `coverage_*` file convention.
2. Miri — failure-triage three-bucket detail + flag rationale.
3. Criterion — the 16-harness inventory + full DoS-budget bench pattern.
4. Fuzzing — the 10-target inventory + libfuzzer output cheat sheet.

Cross-linked back from every SKILL.md section header with
`→ reference.md §N`.

---

## 1. Coverage — TSV walkthrough and `coverage_*` convention

Complements SKILL.md §1.

**Interpreting the punchlist.** Output is TSV with four columns:

```text
file                          regions  lines  functions
src/streaming.rs              88.59    87.35   94.32
src/parser/loader.rs          92.34    94.73   91.67
...
12 files below 98%.
```

`regions` is the most useful column — it counts branch coverage,
so a 100% line-covered file with a missed match arm still shows
up here. `lines` is the usual line count. `functions` catches
public API items nothing calls.

**The gap-report script threshold** (98% by default) is *tighter*
than the CI floor deliberately — the script exists to keep
pressure on the long tail well above the gate.

**The `coverage_*` convention.** Every `crates/noyalib/tests/coverage_*.rs`
file exists to close a specific gap the report surfaced. Examples
in the tree: `coverage_scanner.rs`, `coverage_loader.rs`,
`coverage_borrowed.rs`, `coverage_final_sweep4.rs`. When you
close a gap:

1. Run `./scripts/coverage-gap-report.sh` first — note the file
   and the exact percentage.
2. Add tests to an existing `coverage_*.rs` matching the module
   (e.g. scanner gap → `coverage_scanner.rs`) or create a new
   `coverage_<topic>.rs`. Do **not** add coverage-driven tests to
   feature-focused integration files.
3. Rerun the report; assert the file dropped off the punchlist.
4. The commit message names the file and the delta
   (`"coverage_scanner: cover UTF-8 BOM branch (98.4→100.0)"`).

**Files intentionally excluded.** `noyalib-wasm/src/lib.rs` (wasm-bindgen
runtime not visible to llvm-cov; covered by `wasm-pack test`)
and the MCP/LSP `protocol.rs` subprocess tests. If you touch these,
the corresponding covering harness is where the assertion belongs.

---

## 2. Miri — failure-triage three-bucket detail + flag rationale

Complements SKILL.md §2.

**Why noyalib runs Miri at all.** `noyalib` has `#![forbid(unsafe_code)]`.
That doesn't make Miri redundant — Miri is checking:

1. **Supply-chain interaction.** `indexmap`, `rustc-hash`, `ryu`,
   `itoa`, `memchr`, `smallvec` all use `unsafe` internally. Miri
   verifies noyalib's *calls into* those crates don't trigger UB,
   aliasing violations, or leaks.
2. **Byte-order sanity.** `MIRI_TARGET=mips64-unknown-linux-gnuabi64`
   simulates big-endian, catching latent assumptions in the SWAR
   decimal parser and structural-bitmask iterator (`u64::from_be_bytes`,
   `wrapping_mul` pipelines).
3. **The "Tier 1" promise.** Turns "Zero unsafe" from a README
   claim into an actively verified invariant.

**Flags noyalib uses.** From `scripts/miri.sh`:

- `-Zmiri-strict-provenance` — catches int↔ptr round-trips.
- `-Zmiri-disable-isolation` — lets tests read the system clock /
  entropy (needed by `rustc-hash`'s seed init and `KeyInterner`).
- `-Zmiri-symbolic-alignment-check` — deliberately **NOT** enabled.
  memchr 2.x's x86_64 SSE2 path fires a false positive because
  Miri's symbolic tracker can't see the runtime alignment
  guarantee. Stacked Borrows, strict provenance and leak
  detection still fire.

**Interpreting failures.** In a forbid-unsafe crate, Miri
failures fall into three buckets:

1. **Test-harness issue.** Most common. A test allocates something
   Miri leak-detects because the test forgot to `drop`. Fix the
   test, not the library.
2. **Upstream dep.** A version bump in `indexmap` / `memchr` may
   flag under a newer Miri. Pin the dep, file upstream, or
   `MIRIFLAGS` around the specific check.
3. **True bug in noyalib.** Rare — but never dismiss without
   reading the entire stack trace. A UB report in a `#[cfg(test)]`
   module is still a signal.

**Rule of thumb.** If Miri fails and the failure is in a dep's
inline `unsafe`, first check whether the same failure reproduces
on the dep's own Miri CI. If not, isolate whether noyalib is
misusing the API (unsound calling convention) versus the dep
having a bona fide bug.

**Focused suite composition.** The default `./scripts/miri.sh`
targets `parser::`, `scanner::`, `value::`, `interner::`, `simd::`
— the highest-leverage modules. A scheduled CI job runs the full
`--lib` suite under Miri weekly.

---

## 3. Criterion — the 16-harness inventory + DoS-budget bench pattern

Complements SKILL.md §3.

**All harnesses in `crates/noyalib/benches/` and one-liner purpose:**

| Harness | Purpose |
|---|---|
| `benchmarks.rs` | Comprehensive sweep of the whole public API (deserialise, serialise, Value ops, Mapping, Number, Tag, Path, Schema, Spanned, anchors). |
| `comparison.rs` | 5-way head-to-head vs `serde_yaml_ng`, `yaml-rust2`, `serde_yml`, `yaml-spanned`, `serde-saphyr`. The headline numbers in `doc/BENCHMARKS.md`. |
| `architecture.rs` | Validates streaming vs AST wins, span overhead, DoS-limit speed, zero-copy scalars. Phase C / Phase D checkpoints. |
| `streaming_vs_value.rs` | `StreamingDeserializer` vs `Value`-then-`T::deserialize`. Small / medium / large fixtures. |
| `borrowed_vs_value.rs` | `BorrowedValue<'a>` (zero-copy) vs owned `Value`. String-heavy shape where borrow pays best. |
| `mapping_key_clone.rs` | v0.0.14 collision-guard fix: proves the merge-key clone gate. See SKILL.md §5(c) worked example. |
| `interner.rs` | Three shapes: `String::from`, `Arc::from(&str)`, `KeyInterner::intern`. Proves the win is the cache, not the `Arc`. |
| `numeric_parse.rs` | SWAR `parse_decimal_{i64,u64}` vs stdlib `FromStr`. 8/19 digits + bulk. |
| `simd.rs` | `find_any_of` throughput vs scalar. Sweeps needle arity × haystack size × density. |
| `structural_bitmask.rs` | 32-byte bitmask + `trailing_zeros` vs memchr loop vs scalar. Order-of-magnitude on the 1 MiB path. |
| `parallel.rs` | Rayon-backed `parallel::parse` vs sequential `load_all_as`. Sweeps doc-count × per-doc-size to find break-even. Needs `--features parallel`. |
| `large_doc_soak.rs` | 1 / 10 / 50 MiB inputs. Not in CI (bandwidth). Guards against quadratic regressions. |
| `incremental_repair.rs` | Phase A `Document::set` (`replace_span`) vs full re-parse baseline. |
| `validation_overhead.rs` | Isolates `Spanned<T>` resolution cost on trailing-error documents. |
| `lossless_u64.rs` | `ParserConfig::lossless_u64_integers` off vs on. Needs `--features lossless-u64`. |
| `v006_features.rs` | `recovery` (strict vs lenient), `sval` (vs serde-Value), `tokio` (async-drain overhead). Needs `--features recovery,sval,tokio`. |

Verify the list against the tree: `ls crates/noyalib/benches/`.

**Reading criterion output.** A typical line:

```text
mapping_key_clone/integer_keys/1000
                        time:   [812.4 µs 815.1 µs 818.2 µs]
                        thrpt:  [1.222 Melem/s 1.226 Melem/s 1.231 Melem/s]
                        change: [+0.42% +0.71% +1.03%] (p = 0.03 < 0.05)
                        Change within noise threshold.
```

- **`time:`** — three-point confidence interval [lower, mean, upper] over the sample.
- **`thrpt:`** — inverse of time, expressed against `Throughput::Elements` or `Bytes`. Only shown if the bench declared `.throughput(...)`.
- **`change:`** — vs the last saved baseline (persisted at `target/criterion/<group>/<id>/base`). Positive is slower.
- **`(p = ... < 0.05)`** — Welch's t-test. `p < 0.05` means the change is statistically significant. But: significance ≠ importance. A `p = 0.001` change of `+0.3%` on a 2 µs bench is noise-adjacent.
- **"Change within noise threshold"** — criterion's own heuristic. Trust it as a *floor*: if criterion says noise, it's noise; if criterion says regression, verify.

**Project rules for perf claims.**

1. **Perf claims require a bench run in the same PR.** README /
   BENCHMARKS.md / release notes numbers get regenerated, not
   copy-pasted from memory.
2. **Same fixture, before *and* after.** Never one-side a
   comparison. Regenerate the baseline immediately before the
   change (`cargo bench -- --save-baseline before`), apply the
   change, rerun (`cargo bench -- --baseline before`).
3. **Publish only what you measured on the machine you named.**
   `doc/BENCHMARKS.md` names Apple M4 / Rust 1.95 stable / LTO=fat.
   Numbers gathered elsewhere are useful for regression, not for
   headline claims.

**DoS-budget trap in benches.** `<<`-heavy shapes and >1000-doc
streams trip default `ParserConfig` budgets. If you see
`Error::RepetitionLimitExceeded` (alias expansions),
`Error::Budget(BudgetBreach::MaxDocuments { .. })`, or
`Error::Budget(BudgetBreach::MaxMergeKeys { .. })` mid-bench,
that's a **budget, not a perf regression**. Lift the budget
explicitly in the bench (see `mapping_key_clone.rs`'s
`permissive_config()`):

```rust
let mut cfg = ParserConfig::default();
cfg.max_alias_expansions = 100_000;
cfg.max_merge_keys = 100_000;
```

Then the DoS-limit path itself gets its own bench (e.g. the
"billion-laughs rejection speed" row in `architecture.rs`) so
the budget's *cost* is measured separately from what it's
gating.

---

## 4. Fuzzing — the 10-target inventory + libfuzzer output cheat sheet

Complements SKILL.md §4.

**All targets in `fuzz/fuzz_targets/` and one-liner purpose:**

| Target | Purpose |
|---|---|
| `fuzz_parse` | `from_str::<Value>` panic surface — the smoke test everything else specialises. |
| `fuzz_roundtrip` | `parse(emit(parse(s)))` — output must re-parse without error. Catches serialiser bugs. |
| `fuzz_from_value` | `from_value::<Config>` type coercion; also `Vec<Value>`, `HashMap<String, Value>`. |
| `fuzz_multi_doc` | `---` / `...` boundary detection, per-document anchor scope, `to_string_multi` round-trip. |
| `fuzz_strict` | Tight `ParserConfig` (depth 16, doc 4KiB, aliases 8, mapping 64, seq 64) — DoS budgets under adversarial input. |
| `fuzz_borrowed_alias` | Borrowed-path alias resolution + bomb defence. Prefixes `anchors:\n  - &x ` so libfuzzer explores anchor-heavy inputs. |
| `fuzz_double_quoted` | Double-quoted scalar escape branches, especially JSON-style `\uXXXX\uXXXX` surrogate pairing. |
| `fuzz_yaml_v1_1` | `YamlVersion::V1_1` bundle + each legacy flag in isolation (`legacy_booleans`, `legacy_octal_numbers`, `legacy_sexagesimal`). |
| `fuzz_diff` | **Differential** vs `serde_yaml_ng` / `saphyr`. Flags valid divergences where all parsers accept but produce different shapes. |
| `fuzz_no_span_loader` | **Cross-path** internal differential: `from_str::<Value>` (NoSpanLoader fast path) vs `cst::parse_document` must agree accept/reject. Divergence = parity bug. |

Verify the list against the tree: `ls fuzz/fuzz_targets/`.

**Two differential philosophies.**

- **`fuzz_diff` — external divergence.** noyalib vs the rest of the
  Rust YAML ecosystem. A divergence is *data*, not necessarily a
  bug: noyalib is the most spec-compliant of the three, and both
  `saphyr` and `serde_yaml_ng` have historical quirks. Each
  divergence resolves as: noyalib regression, competitor bug, or
  uncovered spec corner.
- **`fuzz_no_span_loader` — internal divergence.** noyalib's two
  own paths (`from_str::<Value>` streaming NoSpanLoader vs
  `cst::parse_document` span-full CST loader). These are supposed
  to be lock-step. **Any** divergence is a parity bug. See
  SKILL.md §5(a) for the worked example this target was written
  to lock down.

**Common flags.**

- `-max_total_time=<sec>` — wall-clock cap. Local iteration: 30-60s.
- `-timeout=<sec>` — per-input timeout. Default 25s. Lower to 5s
  for `fuzz_parse` to keep the campaign moving.
- `-jobs=<n>` — parallel workers.

**Reading libfuzzer output.**

```text
#123456 REDUCE cov: 4831 ft: 12442 corp: 823/38Kb lim: 4096 exec/s: 12345
```

- **`#123456`** — total execs since campaign start.
- **`cov:` / `ft:`** — coverage counters (edges / features). *Growing* is progress; *flat for 10 seconds* is diminishing returns.
- **`corp:` A/B Kb** — A inputs, B KiB total. Corpus grows as libfuzzer finds novel edges.
- **`exec/s:`** — throughput. If this crashes, look at the target's per-input cost.
- **`REDUCE`** — libfuzzer trimmed an existing corpus entry.
- **`NEW`** — genuinely new coverage.

**Crashes land in `fuzz/artifacts/<target>/`.** Each crash is a raw
byte file named `crash-<hash>`. Reproduce with:

```sh
cargo +nightly fuzz run fuzz_no_span_loader fuzz/artifacts/fuzz_no_span_loader/crash-abc123 \
    --target aarch64-apple-darwin
```

Every artifact should be minimised (`cargo fuzz tmin`) and lifted
into a regression test in `crates/noyalib/tests/scanner_panic_regressions.rs`
before landing the fix.

**Corpus policy.** `fuzz/corpus/` is `.gitignore`d. The seed
inputs live in `fuzz/corpus/seed/` and *are* committed. The
`fuzz/artifacts/` directory is the crash-vault and is committed;
never `rm -rf` it.

CI runs a 10s smoke pass of every target per PR. Long-form runs
(hours per target) are operator-driven before releases.
