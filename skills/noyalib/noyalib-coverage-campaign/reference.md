> Reference material complementing
> `/Users/seb/Code/Public/rust/noyalib/.claude/skills/noyalib-coverage-campaign/SKILL.md`.
> Split extracted 2026-07-08. Load this file only when the compact
> guidance in SKILL.md is insufficient — bucket walkthroughs,
> verbatim house-pattern snippets, "why not" rationale for wrong
> paths, extended solution-menu with when-to-prefer notes, and the
> `invariant_violated` file:line inventory.

---

# Reference: noyalib-coverage-campaign

## 1. Gap-classification decision tree — extended walkthroughs

The Phase 2 four-bucket classification (SKILL.md §Phase 2) is the
single decision that drives the rest of the campaign. Each branch
below expands on the terse table row with signals, examples, and
the failure mode of confusing it with an adjacent bucket.

### (a) Reachable error path

**Signal.** An `Err(Error::…)` return, a `bail!()` on bad input,
a `return Err(Error::new(ErrorKind::Foo, ...))` inside a `match`
arm that fires on user input. The uncovered region is *inside* an
arm that a specific input can trigger.

**Distinguishing feature vs (c).** The arm is NOT annotated with
`#[cfg_attr(noyalib_coverage, coverage(off))]` and it does NOT
call `crate::error::invariant_violated`. It returns an `Err`, and
the `Err` variant is something the caller is expected to handle
(malformed YAML, exceeded limit, unknown tag).

**Action.** Write an integration test in
`crates/noyalib/tests/coverage_<slug>.rs` that constructs the
exact triggering input and asserts the `ErrorKind` variant via
`matches!`. The `matches!` shape is non-negotiable — comparing
against a stringified `Display` locks in error messages and is
brittle.

**Common trap.** Testing "some error came back" instead of "this
error came back". A `.is_err()` assertion closes the coverage but
would still pass if the parser returned the wrong `ErrorKind`.

### (b) Feature-gated code

**Signal.** `#[cfg(feature = "…")]` or `#[cfg(target_arch = …)]`
above the uncovered region. `--all-features` covers the feature
axis but not the target-arch axis.

**Action.** For `feature = "…"`: confirm the campaign's
`make coverage-gap` uses `--all-features` (the script does). If a
gap persists under `--all-features`, the feature-gate is nested
under a `cfg(any(feature = "x", feature = "y"))` with mutually
exclusive features — those need a feature-matrix leg (see
`shared-coverage.yml` matrix).

For `#[cfg(target_arch = …)]`: out of scope for this campaign.
PLAN.md §7.8 tracks cross-target coverage as a separate future
workstream. Document the file as at-ceiling and move on.

**Common trap.** Adding a `#[cfg(feature = "…")]` to make a test
opt-in and calling it done. If the feature is on by default in
`--all-features`, the region is covered anyway; if it isn't,
you've moved the problem, not solved it.

### (c) Defensive-unreachable

**Signal.** A wildcard `_ =>` arm inside a `match` on an internal
enum, whose body calls `crate::error::invariant_violated(...)`
with a static message describing which invariant would have to be
broken to reach it. The parser / builder / deserializer has
already validated the enum shape by construction; the arm exists
to satisfy Rust's exhaustiveness checker.

**Signature form (from `src/error.rs:1697`):**

```rust
#[cfg_attr(noyalib_coverage, coverage(off))]
pub(crate) fn invariant_violated(msg: &'static str) -> ! {
    // ... always panics with a specific, static message.
}
```

Every call site is guarded by the same `coverage(off)` cfg-attr,
so llvm-cov excludes it from the denominator entirely.

**Action.** Do NOT try to hit it. Confirm the annotation is in
place. If it isn't, that's the bug — annotate it. Document
the exclusion in the PR description with the file:line reference.

**Common trap.** Writing an `unsafe` block or a hand-crafted
"impossible" enum value to force the arm to execute. This is
uniformly rejected in review — it also invalidates the safety
argument that lets `invariant_violated` be marked `-> !`.

### (d) Genuinely dead code

**Signal.** Code you can prove no input can reach, and which is
NOT defensive-unreachable — no invariant, no `_ =>` arm, just
leftover from a refactor.

**Action.** Do not test it. Open a change-control PR to remove
it. Coverage rises by subtraction; the codebase gets smaller;
future readers don't have to wonder what it's for.

**Common trap.** Assuming (d) when it's actually (a). Rule of
thumb: if you're not 100 % sure, write the test first. If the
test cannot be written because no input reaches the region,
you've proved (d) empirically. If it can, it was (a) all along.

---

## 2. House pattern — verbatim reference snippets

The canonical style references live in
`crates/noyalib/tests/coverage_scanner.rs`,
`crates/noyalib/tests/coverage_error.rs`, and
`crates/noyalib/tests/coverage_loader_full.rs`. When a new
coverage test file is being authored, mirror these three.

### File header (mandatory)

```rust
//! Coverage tests targeting `src/parser/loader.rs` error paths that only
//! trigger on the AST fallback (triggered by `Spanned<T>`, tags, complex
//! merges, or the `document` module's `load_all*` family).

// SPDX-License-Identifier: MIT OR Apache-2.0
// Copyright (c) 2026 Noyalib. All rights reserved.
```

- The module doc-comment must name the source file(s) whose gaps
  the test file closes. "Coverage tests" alone is not enough — a
  future reader needs to know *why this file exists*.
- SPDX header is non-optional; the repo's `deny.toml` / license
  checks reject files without it.

### Error-path test (assert the variant)

```rust
#[test]
fn duplicate_key_strict_returns_typed_error() {
    let cfg = ParserConfig::new().duplicate_key_policy(DuplicateKeyPolicy::Error);
    let err = from_str_with_config::<Value>("a: 1\na: 2\n", &cfg).unwrap_err();
    assert!(matches!(err.kind(), ErrorKind::DuplicateKey { .. }));
}
```

- `matches!` on the `ErrorKind` variant, not `err.to_string()`.
- Descriptive name — `duplicate_key_strict_returns_typed_error`
  says exactly which behaviour is being asserted.

### Explicit anti-pattern (reject in review)

```rust
#[test]
fn parses_some_yaml() {
    let _ = from_str::<Value>("foo: bar");
    // NO ASSERTIONS — this is the anti-pattern.
}
```

This test executes lines but locks in nothing. If `from_str`
started silently returning wrong values tomorrow, this test
would still pass. Reject.

### Deliberate "any outcome is fine" form (rare, must be documented)

Acceptable only when the test's real assertion is "does not
panic" and either `Ok` or `Err` is a valid outcome. Wrap in a
`catch_unwind` guard or a comment explaining the intent:

```rust
// See coverage_scanner.rs::mapping_value_context_error for the
// honest form: a doc-comment explaining that either outcome is
// acceptable but the parser MUST NOT panic on this input.
```

### Doctest as a coverage tool

If the file being covered exposes a public API without a
`# Examples` block, adding a doctest closes the coverage gap AND
moves rustdoc coverage toward the PLAN.md §1 goal
(`missing_docs = warn` → `deny`, ≥ 98 % items). Double-counting;
prefer this route for anything on the crate's public surface.

---

## 3. `invariant_violated` file:line inventory (2026-07-08)

Grep target for confirming existing sites before adding a new
annotation. All sites below are already annotated
`#[cfg_attr(noyalib_coverage, coverage(off))]` at the `fn`
declaration (`crates/noyalib/src/error.rs:1697`); the call sites
inherit the exclusion by virtue of calling into an excluded fn.

| file                                              | line | context                                    |
|---------------------------------------------------|-----:|--------------------------------------------|
| `crates/noyalib/src/error.rs`                     | 1697 | the `pub(crate) fn` declaration itself     |
| `crates/noyalib/src/borrowed.rs`                  |  686 | `_ =>` arm in a scalar-shape `match`       |
| `crates/noyalib/src/borrowed.rs`                  |  735 | `_ =>` arm in a mapping-shape `match`      |
| `crates/noyalib/src/borrowed.rs`                  |  828 | `_ =>` arm in a nested value `match`       |
| `crates/noyalib/src/parser/events.rs`             |  395 | inside the events dispatch                 |
| `crates/noyalib/src/cst/builder.rs`               |  316 | CST builder wildcard arm                   |
| `crates/noyalib/src/de/deserializer.rs`           |  840 | deserializer wildcard arm                  |

Before annotating a NEW defensive arm, confirm the pattern
matches these seven: internal-enum `match`, `_ =>` wildcard,
`invariant_violated` with a static `&'static str` explaining the
broken invariant, no user input can reach it. If any of those
four is false, it isn't (c) — reclassify.

---

## 4. Known wrong paths — "why not" rationale

Terse list is in SKILL.md §"Known wrong paths (fenced)". This
section expands the *reason* each is wrong so a future session
doesn't relitigate the decision.

### Chasing 100 %

Why not: `invariant_violated` shapes are excluded by policy
(§3 inventory), so 100 % is unreachable *by construction*. The
denominator excludes them. The ceiling on each axis is
practically ≥ 98 % — the target declared in PLAN.md §1. Spending
a session driving a file from 99.7 % → 100 % is time that would
have moved a tier-S file from 92 % → 98 %.

### Weakening thresholds to pass

Why not: The `fail-under-*` numbers in `shared-coverage.yml` and
`doc/TESTING.md` are a one-way ratchet. Lowering them to
paper over a red PR is a security-posture regression (memory
`feedback_security_first_posture`) — the campaign's whole point
is to move them *up*. Any downward motion is a change-control
event requiring maintainer sign-off and a documented reason.

The threshold in `scripts/coverage-gap-report.sh` (`${1:-98}`
default) is also contract — see §4.5 below.

### Assert-free coverage tests

Why not: *Wrong-but-green* is the declared enemy. A test that
executes lines but asserts nothing locks in whatever behaviour
currently exists, correct or not. If the parser silently changes
its output tomorrow, the test still passes and the regression
ships. Coverage numbers rise; correctness confidence falls.
This is the worst possible trade.

### Duplicating existing coverage under a new name

Why not: The house pattern already has ~20 files
(`coverage_scanner.rs`, `coverage_error.rs`, etc.). Adding
`coverage_final_sweep5.rs` that overlaps `coverage_scanner.rs`
proliferates files without adding signal, makes future gap
attribution harder, and breaks the "topic-scoped names" rule
(SKILL.md §Phase 3 "Naming"). Grep first; extend if it exists.

### Testing `invariant_violated` arms directly

Why not: They are marked `-> !` under the safety argument that
no input can reach them. Constructing an "impossible" input via
`unsafe` or hand-forged enum values *invalidates that argument*
— you've created the impossible input, which means the arm was
reachable, which means the panic-safety story collapses. The
correct fix for a defensive arm without annotation is
annotation, not a test.

### Touching `${1:-98}` in `coverage-gap-report.sh` silently

Why not: The default is contract with the maintainer — it's the
aspirational target the campaign is driving toward. Changing it
without change-control moves the goalposts; changing it *down*
is a security-posture regression per
`feedback_security_first_posture`. The 98 is not a preference,
it's the number PLAN.md §1 committed to.

### Bundling with unrelated refactors

Why not: Coverage PRs must be trivially revertible per-file if a
test turns out to be flaky. A PR that adds three coverage files
AND refactors the loader is not revertible — reverting to drop
the flaky test also drops the refactor. Memory
`feedback_no_premature_phasing` says don't over-phase; its
inverse says don't under-phase either. Two logical changes = two
PRs.

---

## 5. Solution menu — when to prefer each

The ranked list in SKILL.md gives the order. This section
expands the *when-to-prefer* judgement calls.

### 1. Targeted unit / integration test

Prefer when: the gap is a single specific input triggering a
single specific behaviour. Fastest to write, most precise
assertion, matches the house pattern verbatim. Use for (a)
reachable-error-path gaps and any single-function invariant.

Avoid when: the gap is a family of related shapes — you'd end up
writing 15 near-identical tests. That's proptest territory.

### 2. Proptest generator

Prefer when: the gap is *shape-family* rather than
*specific-shape*. A single prop check with a generator over
scalar shapes (`single_quoted | double_quoted | plain | literal
| folded`) × chomping-indicator (`- | + | (none)`) × indent-
indicator (`1..=9`) closes dozens of regions in one test. Same
for escape-sequence coverage in double-quoted scalars, or YAML
type-tag combinations.

Avoid when: the failing behaviour is a specific-shape edge case
that proptest is unlikely to hit even with 10 000 iterations
(deep-nested aliases, specific merge-key orderings). Use §4
fixture-driven instead.

Refer to **noyalib-validation-and-qa** for the project's
proptest layer setup — out of scope for this skill.

### 3. Doctest on the public API

Prefer when: the file being covered has a public function
without a `# Examples` block. Closes the coverage gap AND moves
rustdoc-coverage toward the PLAN.md §1 goal in the same commit.
Double-win; the preferred route for anything on the crate's
public surface.

Avoid when: the target is `pub(crate)` or private — doctests
don't run on those. Also avoid for error-path testing where the
example would document a *failing* usage pattern (public docs
should showcase success paths).

### 4. Fixture-driven spec test

Prefer when: the interesting behaviour is the *interpretation*
of a specific YAML document — anchor / alias corner cases,
merge-key ordering, tag resolution, spec-clause edge cases. A
fixture file under `crates/noyalib/tests/fixtures/` plus an
assertion against the expected event stream or `Value` is the
surgical version of the industrial-scale `yaml-test-suite`
compliance harness.

Prefer surgical (single fixture) when the gap is one spec
clause; prefer the compliance harness (out of scope for this
skill — see **noyalib-validation-and-qa**) when the gap is
whole-spec conformance.

### Combining techniques

None of these ranks replaces the others. A well-covered file
often uses all four:

- doctests on the public API (rank 3),
- proptest for the shape family (rank 2),
- targeted integration tests for the specific error variants
  (rank 1),
- fixture-driven tests for the spec-clause corner cases (rank 4).

The rank is the order of *first attempt*, not exclusivity.

---

## 6. Extended error triage (Phase 0 tooling, Phase 4 ceiling)

### Phase 0 — `make coverage-gap` failure modes

- **Toolchain mismatch** — `error: no matching package … nightly` or
  similar. The pin in `rust-toolchain.toml` is stable; re-run with
  `cargo +nightly` (the script already does). If `+nightly` itself is
  missing: `rustup toolchain install nightly --component
  llvm-tools-preview`. See **noyalib-build-and-env** for the full
  toolchain matrix.
- **Numbers wildly off vs the ~96/94/93 baseline** — almost certainly
  ran with a feature subset. Confirm the invocation used
  `--all-features` (the script does; a hand-typed `cargo llvm-cov`
  might not).
- **`--ignore-filename-regex '' → "empty string is not allowed"`** on
  a future llvm-cov — the workflow handles this conditionally with an
  `if [ -n "$X" ]` guard; the script may need the same. Do NOT "fix"
  by removing the flag.
- **CI cache poisoning** — `cargo check` completes in under 2 s yet
  numbers drift. Per memory `feedback_ci_cache_poisoning`, the
  Swatinem cache may be crossing coverage / non-coverage boundaries.
  Coverage jobs isolate via `CARGO_TARGET_DIR=target-coverage` (see
  `shared-coverage.yml`); locally, `cargo clean` and rerun.

### Phase 4 — last-percent ceiling causes

- **`#[cfg(target_arch = …)]`-gated lines** — `--all-features` covers
  the feature axis but not the target-arch axis. Cross-target coverage
  is out of scope for this campaign (PLAN.md §7.8 tracks it as a
  separate future workstream). Document as at-ceiling.
- **Macro-expanded lines** — `llvm-cov show` sometimes reports a
  region inside a `macro_rules!` expansion as uncovered when in fact
  the macro's callers all cover it. Known llvm-cov quirk; document
  the file as at-ceiling in the PR and move on.
- **`#[cfg]`-conditional match variants** — branch coverage on `match`
  arms with feature-conditional variants may need a run under a
  different subset (e.g. `--no-default-features --features alloc` for
  the `no_std` leg, per memory `feedback_ci_cache_poisoning`). Only
  worth the churn if the file is a tier-S module.

---

## 7. Cross-references back to SKILL.md

- Phase 0 baseline command → SKILL.md §"Phase 0 — Baseline"
- Phase 2 bucket table (compact) → SKILL.md §"Phase 2 — Gap analysis"
- Phase 3 house-pattern summary → SKILL.md §"Phase 3 — Test authoring"
- Wrong-paths terse list → SKILL.md §"Known wrong paths (fenced)"
- Solution menu ranked list → SKILL.md §"The solution menu (ranked)"
- Provenance → SKILL.md §"Provenance"

Sibling skills (out of this skill's scope):

- **noyalib-validation-and-qa** — proptest / fuzz / Miri / spec-suite layers.
- **noyalib-diagnostics-and-tooling** — llvm-cov flag reference,
  cargo-vet / deny output.
- **noyalib-change-control** — ratchet-PR mechanics, threshold
  lowering approval flow.
- **noyalib-ci-and-release** — pre-push gate command list,
  shared-workflow caller permissions.
