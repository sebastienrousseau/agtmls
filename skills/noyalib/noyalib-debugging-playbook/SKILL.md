---
name: noyalib-debugging-playbook
description: |
  Symptom-driven triage for noyalib (pure-Rust YAML 1.2). Load when a
  test fails, a parse result surprises you, spans point at the wrong
  bytes, budget errors fire unexpectedly, `from_str::<Value>` and
  `from_str::<MyStruct>` disagree, `no_std` breaks despite green CI
  (symptom triage here; the cache-poisoning CI doctrine that PREVENTS
  it lives in noyalib-ci-and-release), column desync / spurious
  indent errors show up, or you need to
  answer "why does the parse differ?" quickly. Runbook voice with the
  rationale embedded — for a mid-level engineer or Sonnet-class model
  with zero project context.
date: 2026-07-07
---

# noyalib debugging playbook

Repo: `/Users/seb/Code/Public/rust/noyalib` — pure-Rust YAML 1.2
library, workspace `crates/noyalib`, current release `v0.0.14`.

> **Reference material** (full 6-row loader-routing table, full 14-row
> symptom table, full 12-knob/6-variant budget inventory, and traps
> (d) `NaN` key equality + (e) `cargo vet fmt` strips TOML comments):
> see `reference.md` in this directory. Load when the top-N runbook
> paths below don't pin the bug, when you need the exhaustive symptom
> row set, or when you need the complete `BudgetBreach`-vs-other-Error
> mapping.

## THE cardinal triage question

> **Which of the THREE loaders is my bug in?**

`from_str_with_config` in `crates/noyalib/src/de.rs` routes to one of
three code paths. Almost every "same input, different result" report
resolves once you know which path fired.

The routing decision lives around `de.rs:396-499`. Read it — it
changes. As of v0.0.14 the shape is:

```rust
// crates/noyalib/src/de.rs (approx line 415)
let value_target_bypass = is_value_target::<T>() && config.tag_registry.is_none();
let stream_eligible = config.merge_key_policy == MergeKeyPolicy::Auto
    && !config.ignore_binary_tag_for_string
    && config.policies.is_empty()
    && properties_inactive(config)
    && includes_inactive(config)
    && !value_target_bypass;
```

### Routing table (top 3 rows — full 6-row matrix in `reference.md` §routing-full)

| T                          | Config knobs                                       | Path                                 | Where                                           |
| -------------------------- | -------------------------------------------------- | ------------------------------------ | ----------------------------------------------- |
| any typed `T` (not `Value`) | all defaults                                       | **streaming** (`streaming.rs`)       | `de.rs` `stream_eligible == true`               |
| `Value`                    | `tag_registry.is_none()` (i.e. no registry active) | **`NoSpanLoader`** (span-free)       | `de.rs:454` `is_value_target::<T>()` fast path  |
| any typed `T`              | any non-default config knob above                  | **`Loader`** (span-full) then serde  | `de.rs:472` `#[cfg(feature = "std")]` block     |

Nuance you will hit: **v0.0.14 excludes `Value`-target from streaming
unless a TagRegistry is active.** The `NoSpanLoader` owns the
distinct-typed `KeyCollision` guard and the DoS budgets. See
`bc8f798 fix(loader): plug distinct-typed key collision on Value fast
path`. Rationale + `Spanned<T>` / `Value`+registry / CST rows: see
`reference.md` §routing-full.

### The discriminating experiment

Feed the same input through all three loaders and diff:

```rust
let v_value: Result<Value, _>       = noyalib::from_str::<Value>(src);
let v_typed: Result<MyStruct, _>    = noyalib::from_str::<MyStruct>(src);
let v_cst:   Result<Document, _>    = noyalib::cst::parse_document(src);
```

Divergence localises the bug:

- **`Value` OK, typed Err** → streaming deserializer (`streaming.rs`).
- **`Value` Err, CST OK** → `NoSpanLoader` vs green-tree walker
  divergence; `dup_key_spans.rs` is the canonical parity suite.
- **`Value` OK, CST Err** → span-full path or CST-specific walk.
- **All three disagree on numbers/bools** → scalar resolution split
  across three sites; check `1225-1367` in `parser/loader.rs`.

This is exactly the cross-check `fuzz/fuzz_targets/fuzz_no_span_loader.rs`
runs; it exists because the silent-collapse bug survived 4000+ green
tests when no test compared `Value` and CST paths directly.

## Symptom table

The top 5 rows by hit rate are below; the **full 14-row table** with
every variant (span-fix rows for `f8fe929` / `1f76951` / `af7a9bd` /
`1d72687`, `no_std` cache poisoning, scanner CR/BOM row, budget-error
wart row, `next_value_seed` misuse, `RecursionLimitExceeded` on
shallow-but-wide) is in `reference.md` §symptom-full. Each row cites
the file/test/commit that pins the behaviour so you can verify against
source, not against my memory.

| Symptom | Likely cause | First check | Verify against |
| ------- | ------------ | ----------- | -------------- |
| "Parses but data missing (some keys gone)" | `DuplicateKeyPolicy` collapsing genuine duplicates, or (pre-0.0.14) distinct-typed collision silently overwriting | Set `config.duplicate_key_policy = DuplicateKeyPolicy::Error` and re-run | `tests/dup_key_spans.rs::distinct_typed_keys_collide_loudly` (`crates/noyalib/tests/dup_key_spans.rs:186`) |
| "Works as `struct T`, fails as `Value`" (or vice versa) | Loader divergence — streaming vs `NoSpanLoader` vs `Loader` | Run the discriminating experiment above | `tests/no_span_loader_parity.rs` (`crates/noyalib/tests/no_span_loader_parity.rs`) |
| "Span points at wrong bytes" | CST walker; five separate fixes landed in v0.0.14 cycle | `git log --oneline -20 -- crates/noyalib/src/cst/` | Commits `f8fe929`, `1f76951`, `af7a9bd`, `1d72687` |
| Span includes trailing blanks | `span_at` trims trailing blanks; raw event spans don't | Compare `doc.span_at(path)` vs `Spanned<T>` extents | `tests/dup_key_spans.rs::spanned_fields_stay_aligned_after_duplicate_key` |
| "Budget error unexpectedly" | One of the 12 `ParserConfig` budget knobs fired (only **6** flow into `BudgetBreach`; others surface as `RecursionLimitExceeded`, `RepetitionLimitExceeded`, `Serialize`, or `Parse` — see budget summary below) | Read the error message + variant | `crates/noyalib/src/error.rs:161` `BudgetBreach` enum |

### Budget inventory (summary)

Load-bearing counts: `ParserConfig` has **12** budget knobs; only **6**
of them flow through `Error::Budget(BudgetBreach::...)`
(`MaxEvents`, `MaxNodes`, `MaxTotalScalarBytes`, `MaxDocuments`,
`MaxMergeKeys`, `AliasAnchorRatio`) at `crates/noyalib/src/error.rs:161`.
The other 6 surface elsewhere:

- `max_depth` → `Error::RecursionLimitExceeded`
- `max_alias_expansions` → `Error::RepetitionLimitExceeded`
- `max_mapping_keys` / `max_sequence_length` → **`Error::Serialize`**
  (spelling wart — callers pattern-match on `msg.contains(...)`; do
  not "fix" without checking callers)
- `max_document_length` → `Error::Parse`
- `max_include_depth` → include-feature specific

Full knob-by-knob mapping, `BudgetBreach` variant field shapes, the
exact wart-message strings, and the test lines that assert them: see
`reference.md` §budget-full.

## Traps with stories

### (a) `cargo fuzz` needs an explicit target on Apple Silicon

**Trap:** Running `cargo +nightly fuzz run fuzz_no_span_loader` on an
M-series Mac errors with `E0463: can't find crate for 'std'`.

**Why it bites:** `cargo fuzz` defaults to `x86_64-apple-darwin`;
recent nightlies don't ship that std by default on Apple Silicon. The
error mentions `std`, not `target`, so it looks like a toolchain bug.

**Avoid:** always pass `--target aarch64-apple-darwin` on Apple
Silicon:

```
cargo +nightly fuzz run fuzz_no_span_loader --target aarch64-apple-darwin -- -max_total_time=60
```

### (b) Tests passing does not mean correct — cross-loader parity is the load-bearing check

**Trap:** the distinct-typed key silent-collapse (`1: a` then `"1": b`
overwrites) survived 4000+ green tests.

**Why it bites:** every test looked at one loader in isolation. The
`Value`-typed tests exercised `NoSpanLoader`; the struct-typed tests
exercised streaming; the span tests exercised `Loader`. None compared
outputs across paths, so an entry silently vanishing on one path but
being caught on another produced 100% green.

**Avoid:** any behavioural fix that touches key handling, budgets, or
collision must add a parity test to `tests/no_span_loader_parity.rs`
AND update `fuzz/fuzz_targets/fuzz_no_span_loader.rs` (which
cross-checks `from_str::<Value>` vs `cst::parse_document`).

### (c) `cwd` left in `fuzz/` breaks `cargo` — "not a member of the workspace"

**Trap:** After a fuzz session you run `cargo test -p noyalib` and get
`error: package ID specification 'noyalib' did not match any packages`
or `current package believes it's in a workspace when it's not`.

**Why it bites:** `fuzz/Cargo.toml` is its own crate outside the
workspace. If your shell is still in `fuzz/`, cargo picks up that
manifest instead of the workspace root.

**Avoid:** `cd "$(git rev-parse --show-toplevel)"` at the top of any
multi-step script. Every noyalib maintenance script (`.git/*.sh`)
starts with that line for exactly this reason.

Two more traps — (d) `NaN` key equality is a landmine for the
collision check (why we don't use `HashSet<Value>` for key dedup),
and (e) `cargo vet fmt` strips TOML comments so exemption rationale
must go in the commit — are in `reference.md` §traps-extended.

## Discriminating experiments — copy-paste commands

Always run from the workspace root:

```
cd "$(git rev-parse --show-toplevel)"
```

### Minimal reproducer template

```rust
// tests/scratch_repro.rs   (put in crates/noyalib/tests/)
use noyalib::{Value, from_str, cst::parse_document};

#[test]
fn repro() {
    let src = "PUT_YAML_HERE\n";
    let v  = from_str::<Value>(src);
    let d  = parse_document(src);
    eprintln!("value = {v:#?}");
    eprintln!("cst   = {:?}", d.as_ref().map(|d| d.to_string()));
}
```

Run one focused test with backtrace and stdout:

```
RUST_BACKTRACE=1 cargo test -p noyalib --test dup_key_spans -- --nocapture
RUST_BACKTRACE=1 cargo test -p noyalib --test no_span_loader_parity distinct_typed_key_collision -- --nocapture
RUST_BACKTRACE=1 cargo test -p noyalib --test issue_46 no_span_loader_honours_max_depth -- --nocapture
```

Run one fuzz target for 60s (Apple Silicon):

```
cargo +nightly fuzz run fuzz_no_span_loader \
  --target aarch64-apple-darwin -- -max_total_time=60
```

For x86_64 hosts drop `--target`.

Inspect the routing gate (re-verify after any de.rs change):

```
grep -n "stream_eligible\|is_value_target\|value_target_bypass" crates/noyalib/src/de.rs
```

Cross-loader smoke check on a single input, one-shot:

```
cargo test -p noyalib --test no_span_loader_parity -- --nocapture
```

CST span probe from a REPL-ish test:

```rust
let doc = noyalib::cst::parse_document(src).unwrap();
if let Some((s, e)) = doc.span_at("some.path") {
    eprintln!("[{s}..{e}] = {:?}", &doc.source()[s..e]);
} else {
    eprintln!("no span for path");
}
```

## When NOT to use this skill

- **For the full history of settled investigations** (why a fix is
  shaped the way it is, what earlier attempts failed) →
  `noyalib-failure-archaeology`.
- **For measuring instead of guessing** (benchmarks, allocation
  profiles, flamegraphs) → `noyalib-diagnostics-and-tooling`.
- **For release / version-bump mechanics** → `noyalib-change-control`.

This skill is scoped to *"what broke, where do I look, what
experiment discriminates?"* — not history, not measurement, not
release choreography.

## Provenance and maintenance

This provenance section covers **both** `SKILL.md` and `reference.md`
in this directory — one truth source for the split.

**Ground-truth files consulted** (verify each still says what this
skill claims when you update it):

- `crates/noyalib/src/de.rs` — routing gate `stream_eligible`
  (~L415), `is_value_target` (L170), `Value`-target fast path (L454).
- `crates/noyalib/src/parser/loader.rs` — `Loader` struct (L241),
  `NoSpanLoader` struct (L861), `NoSpanFrame::typed_keys` parallel
  vec (L843), budget spellings (L575, L675, L1063, L1135).
- `crates/noyalib/src/streaming.rs` — `raw_str_mode` in
  `next_key_seed` (L1346-1348), `finished` guard on
  `next_value_seed` (L1363).
- `crates/noyalib/src/cst/document.rs` — `span_at` (L193),
  `resolve_path_in_green` + typed-cache fallback (L201-L211),
  `trim_value_span` behaviour.
- `crates/noyalib/src/error.rs` — `BudgetBreach` enum (L161),
  `Error::Budget` variant (L542).
- `crates/noyalib/tests/no_span_loader_parity.rs` — parity contract.
- `crates/noyalib/tests/dup_key_spans.rs` — span/typed-view
  alignment on duplicates + distinct-typed collision refusal.
- `crates/noyalib/tests/issue_46.rs` — `NoSpanLoader` depth-limit
  regression + `RecursionLimitExceeded` shape.
- `fuzz/fuzz_targets/fuzz_no_span_loader.rs` — cross-loader
  divergence cross-check.
- Commits: `bc8f798`, `0fff9dd` (distinct-typed collision),
  `f8fe929`, `1f76951`, `af7a9bd`, `1d72687` (five CST span fixes),
  `70c77cb` (lone-CR scanner fix), `3304f4c` (BOM v0.0.10).

**Re-verify the routing table before trusting it** — one command:

```
grep -n "stream_eligible" crates/noyalib/src/de.rs
```

If the surrounding boolean expression grew a new conjunct, update the
routing table above. This is the single most load-bearing claim in
the skill.

Last updated: 2026-07-08 against `feat/v0.0.14`
(`HEAD == 5c41ef3 chore(supply-chain): update cargo-vet exemptions`).
Split into `SKILL.md` + `reference.md` on 2026-07-08.
