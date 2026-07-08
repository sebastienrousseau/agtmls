---
name: noyalib-diagnostics-and-tooling
description: Measure instead of eyeball. Use when running or interpreting coverage, Miri, criterion benchmarks, or cargo-fuzz on noyalib; when proving a fix works (differential testing, budget-breach assertions, bench-gated optimisations, clean-fingerprint verification); when reading tool output (regions/lines/functions percentages, Miri UB reports, criterion time/thrpt/change tables, libfuzzer runs/corpus/artifacts); when a claim needs evidence rather than an assertion.
date: 2026-07-08
---

# noyalib diagnostics and tooling

The "prove it" skill: the four measurement tools (coverage, Miri,
criterion, cargo-fuzz), how to read their output, and the four
proof recipes with worked examples from repo history.

Triaging a symptom → `noyalib-debugging-playbook`. Deciding what
evidence attaches to a PR → `noyalib-validation-and-qa`. This
skill is for the layer between: I know what to measure, how do I
do it, and what does the output mean.

**Extended reference:** the 16-bench inventory, the 10-fuzz-target
inventory, the coverage TSV walkthrough, the Miri three-bucket
detail, the full `permissive_config()` bench pattern, and the
libfuzzer output cheat sheet live in `reference.md` (same
directory). Each section below cross-links to its `reference.md`
counterpart.

## Provenance (regenerate before trusting)

```sh
ls scripts/                                # coverage-gap-report, miri, msrv-per-crate, pgo
ls crates/noyalib/benches/                 # 16 criterion harnesses
ls fuzz/fuzz_targets/                      # 10 libfuzzer targets
```

Counts at date-stamp: **16** harnesses, **10** fuzz targets.
Legacy references to "13 / 9" in `doc/TESTING.md` predate v0.0.14
— the tree is truth. Read for context: `Makefile`, `scripts/miri.sh`,
`scripts/coverage-gap-report.sh`, `doc/BENCHMARKS.md`,
`doc/TESTING.md`.

---

## 1. Coverage — `cargo +nightly llvm-cov`

`scripts/coverage-gap-report.sh` wraps
`cargo +nightly llvm-cov --workspace --all-features --no-fail-fast --summary-only`
and prints the punchlist of files under a percentage threshold.
Runtime ~2 min from a cold cache. Full text of the run is teed to
`/tmp/noyalib-coverage.log`.

```sh
./scripts/coverage-gap-report.sh          # default 98% threshold
./scripts/coverage-gap-report.sh 95       # custom threshold
make coverage-gap                         # same, via Makefile
```

**The workspace CI gate.** Per `.github/workflows/ci.yml:160-162`
and the `shared-coverage.yml` reusable defaults, CI fails under:

- `--fail-under-functions 96`
- `--fail-under-lines 94`
- `--fail-under-regions 93`

(`doc/TESTING.md` still cites `95 / 93 / 92`; that document is
stale. Trust the workflow files.) The gap-report script threshold
(98% by default) is *tighter* than the CI floor deliberately — it
keeps pressure on the long tail well above the gate.

**TSV output format, the `coverage_*.rs` convention, and the
intentionally-excluded files → `reference.md` §1.**

---

## 2. Miri — UB and leak detection under a forbid-unsafe crate

`noyalib` has `#![forbid(unsafe_code)]`, but Miri still matters
because the supply chain (`indexmap`, `rustc-hash`, `ryu`, `itoa`,
`memchr`, `smallvec`) uses `unsafe` internally, and a big-endian
cross-check catches latent byte-order assumptions in the SWAR
decimal parser and structural-bitmask iterator. `scripts/miri.sh`
(or `make miri`) is the wrapper.

```sh
./scripts/miri.sh                                        # focused suite
./scripts/miri.sh simd                                   # simd:: only
MIRI_TARGET=mips64-unknown-linux-gnuabi64 ./scripts/miri.sh
                                                         # big-endian cross-check
make miri-full                                           # full lib suite, slow
make miri-bigendian                                      # same as MIRI_TARGET one-liner
```

The focused suite runs `parser::`, `scanner::`, `value::`,
`interner::`, `simd::` — the highest-leverage modules. A scheduled
CI job runs the full `--lib` suite under Miri weekly.

**Flag rationale (strict-provenance, disable-isolation, why
symbolic-alignment-check is OFF), the three-bucket failure
triage, and the "dep unsafe vs noyalib misuse" rule of thumb →
`reference.md` §2.**

---

## 3. Criterion benchmarks — 16 harnesses in `crates/noyalib/benches/`

Sixteen harnesses cover the public API sweep, the 5-way ecosystem
comparison, streaming vs Value, borrowed vs owned, the interner,
SWAR numerics, SIMD, structural bitmask, parallel, soak,
incremental repair, validation overhead, lossless_u64, v0.0.6
features, and the collision-guard clone gate. Full inventory with
one-liner purposes → `reference.md` §3.

**Running one.**

```sh
# For iteration — one shape, short warm-up:
cargo bench -p noyalib --bench mapping_key_clone -- --quick

# For numbers you'll publish (README / BENCHMARKS.md / release notes):
cargo bench -p noyalib --bench comparison
```

`--quick` uses criterion's short-run mode (fewer iterations, no
outlier analysis). Fine for regression detection; **not** fine for
absolute numbers you cite in prose.

**Baselines for a real comparison.**

```sh
cargo bench -p noyalib --bench comparison -- --save-baseline before
# ... apply change ...
cargo bench -p noyalib --bench comparison -- --baseline before
```

**Ground rule.** Perf claims require a bench run in the same PR,
on the same fixture before *and* after, on the machine
`doc/BENCHMARKS.md` names (Apple M4 / Rust 1.95 stable / LTO=fat).

**Reading `time` / `thrpt` / `change` / `p =` output, the DoS-budget
trap, and the full `permissive_config()` pattern from
`mapping_key_clone.rs` → `reference.md` §3.**

---

## 4. Fuzzing — 10 targets in `fuzz/fuzz_targets/`

Ten libfuzzer targets cover the general parse panic surface,
round-trip, `from_value` coercion, multi-doc boundaries, strict
DoS budgets, borrowed-alias bomb defence, double-quoted escapes,
YAML 1.1 legacy flags, external differential vs the ecosystem
(`fuzz_diff`), and internal cross-path differential
(`fuzz_no_span_loader`). Full inventory with one-liner purposes →
`reference.md` §4.

**Running locally on Apple Silicon.** cargo-fuzz needs an
explicit target on macOS:

```sh
cargo +nightly fuzz run fuzz_no_span_loader \
    --target aarch64-apple-darwin \
    -- -max_total_time=60
```

**External vs internal divergence.** `fuzz_diff` compares noyalib
against `serde_yaml_ng` / `saphyr` — divergence is *data*, not
necessarily a bug. `fuzz_no_span_loader` compares two noyalib
paths (streaming NoSpanLoader vs CST loader) — **any** divergence
is a parity bug. See §5(a) below for the worked example.

**libfuzzer output legend (`cov` / `ft` / `corp` / `exec/s` /
`REDUCE` / `NEW`), crash reproduction, `cargo fuzz tmin`, the
corpus policy, and the CI smoke-pass cadence →
`reference.md` §4.**

---

## 5. Proof-and-analysis recipes

Four recipes, each with a worked example from repo history.
When you are trying to *prove* a claim, one of these fits.

### (a) Cross-path differential testing

**Recipe.** When two code paths claim the same semantics, don't
inspect either — build a harness that feeds identical inputs to
both and compares the outcomes. Automate it so it stays true.

**Worked example — the v0.0.14 NoSpanLoader parity bug.** The
`from_str::<Value>` path had silently gained a span-free
`NoSpanLoader` fast path. It was collapsing distinct-typed key
collisions (`{1: a, "1": b}` merged instead of raising) and
skipping three DoS budgets. The CST loader (`cst::parse_document`)
retained the correct behaviour.

The bug was proven in ~10 lines:

```rust
let s = "1: a\n\"1\": b\n";
let v1 = noyalib::from_str::<noyalib::Value>(s);
let v2 = noyalib::cst::parse_document(s).map(|doc| doc.value());
assert_eq!(v1.is_err(), v2.is_err(), "parity divergence: {s:?}");
```

That reproducer became the seed for `fuzz_no_span_loader.rs`,
which panics on any accept/reject divergence:

```rust
// both accept → OK; both reject → OK; disagreement → PANIC
```

The regression tests live in `crates/noyalib/tests/no_span_loader_parity.rs`.

**When to reach for this.** Two APIs described with the same
verb ("parse", "resolve", "format"), two implementations for
the same spec section, streaming vs materialised, borrowed vs
owned, sync vs async. If they diverge on any input, one of
them is wrong.

### (b) Budget-breach verification

**Recipe.** To prove a DoS budget works, construct the *minimal*
input that exceeds it by exactly one and assert the **exact**
error variant. Don't accept "some error was returned".

**Worked example — `tests/no_span_loader_parity.rs`.** The fast
path had been skipping the alias-expansion, mapping-key, and
document-count checks. The fix wasn't just "add the checks" —
it was "add the checks and prove the exact error surface fires
at N+1 items". Assertion granularity matters: `is_err()` proves
nothing — a totally unrelated parse failure would pass. Only
the exact `Error` variant (and, for `Error::Budget`, the exact
`BudgetBreach` variant) proves *this* budget fired.

Which error surface applies depends on the knob:

- `max_depth` → `Error::RecursionLimitExceeded`.
- `max_alias_expansions` → `Error::RepetitionLimitExceeded`
  (NOT a `BudgetBreach` variant).
- `max_mapping_keys` / `max_sequence_length` →
  `Error::Serialize(...)` (documented wart — see
  `noyalib-architecture-contract` §5.1).
- `max_document_length` → `Error::Parse`.
- `max_documents`, `max_events`, `max_nodes`,
  `max_total_scalar_bytes`, `max_merge_keys`, `alias_anchor_ratio`
  → `Error::Budget(BudgetBreach::{MaxDocuments | MaxEvents |
  MaxNodes | MaxTotalScalarBytes | MaxMergeKeys | AliasAnchorRatio})`.

Example (budget-flavoured knob):

```rust
let cfg = ParserConfig::new().max_documents(2);
let over_by_one = "---\na: 1\n---\nb: 2\n---\nc: 3\n"; // 3 docs, limit 2
let err = noyalib::from_str_with_config::<Value>(over_by_one, &cfg)
    .expect_err("limit must fire");
assert!(matches!(
    err,
    noyalib::Error::Budget(noyalib::BudgetBreach::MaxDocuments { .. })
));
```

Example (`Error::Serialize`-flavoured knob):

```rust
let cfg = ParserConfig::new().max_mapping_keys(4);
let over_by_one = "a: 1\nb: 2\nc: 3\nd: 4\ne: 5\n"; // 5 keys, limit 4
let err = noyalib::from_str_with_config::<Value>(over_by_one, &cfg)
    .expect_err("limit must fire");
assert!(matches!(err, noyalib::Error::Serialize(_)));
```

**When to reach for this.** Any resource limit: `max_depth`,
`max_alias_expansions`, `max_document_length`,
`max_mapping_keys`, `max_sequence_length`, `max_merge_keys`,
`max_documents`, `max_events`, `max_nodes`,
`max_total_scalar_bytes`, `alias_anchor_ratio`,
`max_include_depth`. The pattern is: at-limit input passes,
at-limit-plus-one input raises the exact variant listed above.

### (c) Bench-gated optimisation

**Recipe.** Never trust an optimisation without a criterion run.
Structure it as *three* measurements, not two:

1. **Before, on the shape the optimisation should help.**
2. **After, on the shape the optimisation should help.**
3. **After, on a shape the optimisation should NOT help — the control.**

If (3) regresses, the optimisation has a cost you didn't budget
for.

**Worked example — the v0.0.14 mapping-key clone gate.** The
collision-guard fix added a `Value::clone()` per non-merge
mapping key. The concern: does this regress merge-heavy
documents? `benches/mapping_key_clone.rs` runs two shapes:

- `integer_keys/N` — mapping of N distinct integer keys. Every
  key pays the clone. This is the "shape that should slow down
  a little".
- `merge_heavy/N` — same shape but every key comes through `<<:`
  merge. The `is_buffered_merge_key` gate should skip the clone
  entirely. This is the **control** — it must **not** regress.

The gate proved out: `merge_heavy` stayed within ~15% of the
`integer_keys` shape, confirming the merge-key clone is
genuinely skipped (not just "amortised on average").

**When to reach for this.** Any hot-path change with a plausible
"but does it slow down the other case" — new allocations, new
copies, new type coercions, added match arms in scanner
state machines.

### (d) Clean-fingerprint verification

**Recipe.** When CI and local disagree ("passes on my machine"),
don't debug the difference in your `target/` — rebuild both
sides with a fresh, isolated `CARGO_TARGET_DIR` so incremental
cache is out of the picture.

**Worked example — the CI cache-poisoning gotcha.** A prior
run (recorded in memory: `feedback_ci_cache_poisoning.md`) had
Swatinem's cache action + sub-2s `cargo check` masking a
broken `no_std` build. The fix: scope `CARGO_TARGET_DIR` per
feature-matrix job so each row has its own dedicated cache
namespace and can't inherit stale artefacts from the row above.

Local reproduction of the same technique:

```sh
CARGO_TARGET_DIR=/tmp/nya-clean-$(uuidgen | head -c 8) \
    cargo check --no-default-features --features some-thin-subset
```

If the clean-namespace build fails and the ambient `target/`
build passes, ambient cache is lying to you. Never diagnose
against a poisoned cache — reproduce clean first, then debug.

**When to reach for this.** Feature-matrix mismatches, MSRV
drift, `no_std` builds, cross-target checks, "works on Linux
but fails on macOS" reports, cache-key regressions after a
Swatinem bump.

---

## When NOT to use this skill

- Symptom triage ("parser rejects a document I think is valid") → `noyalib-debugging-playbook`. Come back here once you know what to *measure*.
- What evidence attaches to a PR → `noyalib-validation-and-qa`. This skill tells you *how* to produce a bench / coverage number; that one tells you *which* a given change needs.
- YAML spec / semantic questions → `yaml-domain-reference`.
- CI-config / workflow issues → `noyalib-change-control`. Diagnostic scripts run *inside* CI; the workflow layer that invokes them belongs there.

---

## One-page cheatsheet

```sh
# Coverage
./scripts/coverage-gap-report.sh 98
make coverage-gap

# Miri
./scripts/miri.sh                                       # focused
./scripts/miri.sh simd                                  # module-only
MIRI_TARGET=mips64-unknown-linux-gnuabi64 ./scripts/miri.sh
make miri-full                                          # slow

# Benches
cargo bench -p noyalib --bench mapping_key_clone -- --quick
cargo bench -p noyalib --bench comparison -- --save-baseline before
# ... apply change ...
cargo bench -p noyalib --bench comparison -- --baseline before

# Fuzz
cargo +nightly fuzz run fuzz_no_span_loader \
    --target aarch64-apple-darwin -- -max_total_time=60

# MSRV per-crate
./scripts/msrv-per-crate.sh
./scripts/msrv-per-crate.sh noyalib-lsp
```
