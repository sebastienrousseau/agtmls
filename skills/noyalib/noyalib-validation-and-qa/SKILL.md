---
name: noyalib-validation-and-qa
description: >-
  What counts as evidence in the noyalib repo. Load this BEFORE opening a PR,
  BEFORE claiming a fix is done, and BEFORE adding a test. Covers the evidence bar
  (regression test must fail on the pre-fix tree; wrong-but-green is the enemy),
  the test taxonomy (coverage_*, cst_*, spec/, official_suite, proptest,
  competitor_bugs, de*/ser*, issue_* regressions, ~480 doctests), the certified
  inventory (official YAML Test Suite + benches/fixtures/*.yaml), SPDX-headed file
  naming, doctest rules (# Examples + errors-parse-a-repro from Error::KeyCollision),
  and the acceptance thresholds (coverage 98/98/98 target vs live 96/94/93;
  official-suite floor is the merge gate; clippy -D warnings; rustfmt clean). Use
  for "how do I add a test", "does this need a regression test", "how do I write a
  cross-loader parity test", "what evidence must a PR carry". Not this skill:
  running tools → noyalib-diagnostics-and-tooling; the coverage campaign →
  noyalib-coverage-campaign. v0.0.14, dated 2026-07-08.
---

# noyalib Validation & QA

The evidence bar. A PR that "looks right" is not merged; a PR that
proves a behaviour with a test that would have failed on the previous
tree is. This skill fences that discipline into checklists.

- Audience: mid-level engineer or Sonnet-class model.
- Scope: pure-Rust YAML library `noyalib` v0.0.14, test harness and
  conformance suites.
- Not this skill:
  - Running / interpreting the tools → `noyalib-diagnostics-and-tooling`.
  - The 95 → 98 coverage push specifically → `noyalib-coverage-campaign`.
  - Chronicle of settled fights → `noyalib-failure-archaeology`.
- Date-stamped: 2026-07-07.

> **Reference material** (full 130-file test taxonomy, the official
> YAML Test Suite mechanics + bench-fixture inventory, and the
> read-only provenance one-liners): see `reference.md` in this
> directory. This file keeps the evidence bar, the add-a-test
> checklists, the acceptance thresholds, and what does NOT count.

---

## 1. The evidence bar (non-negotiable)

**A fix is proven by a test that FAILS on the pre-fix tree.** The
discipline is: write the regression test first, watch it fail
(`cargo test <name>` red), then fix, then watch green. `CONTRIBUTING.md`
lines 47–48 codify the rule: *"Add or update tests in the same commit /
PR as the behaviour change. Never as a follow-up."*

There is one caveat driven by the [CI-always-green invariant] captured
in `MEMORY.md`: **red tests never get PUSHED alone.** The red→green
transition happens locally. What lands on `main` is the fix plus its
regression test, both green, in one commit. A reviewer reconstructs the
red state mentally by reading the test and the fix together — the test
name typically encodes the pre-fix bug (e.g.
`from_str_value_refuses_distinct_typed_key_collision`).

**"Wrong-but-green" is the enemy.** The silent key-collision collapse
survived 4000+ green tests because no test compared the two loader
paths against the same input. See
`tests/no_span_loader_parity.rs:1–43` — it now pins that any semantics
shared by two code paths must have a cross-path test. The rule
generalises:

> If a behaviour is implemented by more than one code path
> (span-full loader vs `NoSpanLoader`, streaming vs blocking,
> borrowed vs owned, SIMD vs scalar), the invariant needs a test
> that exercises **both paths against the same input** and asserts
> they agree.

Exemplars to copy:

- `tests/no_span_loader_parity.rs` — loader parity.
- `tests/simd_equivalence.rs` — SIMD/scalar path parity.
- `tests/error_kind.rs` — pins the `Error → ErrorKind` classifier
  (downstream consumers routing on kind).

---

## 2. Test taxonomy

`crates/noyalib/tests/` holds **130 top-level integration test files**
(`ls crates/noyalib/tests/*.rs | wc -l`), every one SPDX-headed, plus
**~480 doctests**. When adding a file, match an existing family:
`coverage_*` (llvm-cov gaps), `cst_*` (green-tree/round-trip/span),
`spec/<area>.rs`, `de*`/`ser*`/`serde*` (serde surface), `issue_<n>`
(incident regressions), `competitor_bugs.rs`, `proptest.rs`, and the
`*_panic_regressions.rs` fuzz corpora. Full family-by-family table with
file counts in `reference.md` §R1.

---

## 3. Certified / golden inventory

The conformance gate is `tests/official_suite.rs` — asserts
`compliance >= 94.0` with an **empty `SKIP_LIST`**; the `README`
"387/387 / 19 skipped" and `BENCHMARKS.md` "406/406" numbers are
documentation drift, so cite the test files (351 wrapper `.yaml` cases,
94% floor), not the prose. Any loaded-case pass-count drop is a release
blocker. Golden bench fixtures live in `benches/fixtures/*.yaml` — do
not mutate without a paired Criterion baseline. Full mechanics (marker
decoder, verbatim assertion arithmetic, companion report, fixture
table) in `reference.md` §R2.

---

## 4. How to add a test — checklists per kind

### 4.1 Integration test (new `.rs` file under `tests/`)

1. Pick the family (`coverage_*`, `cst_*`, `de_*`, `issue_<n>`, spec/,
   competitive_*, etc.) and match its naming. New file **needs the
   exact SPDX header** every existing test carries:

   ```rust
   // SPDX-License-Identifier: MIT OR Apache-2.0
   // Copyright (c) 2026 Noyalib. All rights reserved.

   //! One-line summary — what invariant this file locks.
   //!
   //! Longer context: what was wrong, or what path this covers.
   ```

   (Verify shape against any existing file, e.g. `tests/issue_46.rs` or
   `tests/no_span_loader_parity.rs`.)

2. If it's a bug regression, name the test after the bug and start the
   file's module doc with `//! Regression test for …`.

3. If it's spec-area coverage, put it under `tests/spec/<area>.rs` and
   register the module in `tests/spec/mod.rs`.

4. Feature-gated tests need either `required-features` in
   `Cargo.toml`'s `[[test]]` entry, or `#[cfg(feature = "…")]` inside
   the file. Prefer the `cfg` gate — no manifest churn.

5. Anything touching two code paths (blocking vs streaming, spanned
   vs no-span, SIMD vs scalar) needs a cross-path parity test — see
   `tests/no_span_loader_parity.rs` and `tests/simd_equivalence.rs`.

### 4.2 Spec case

- One `#[test] fn <snake_case_name>()` per assertion.
- File already exists (`tests/spec/scalars.rs` etc.) → add the test
  there. If the area has no file yet, create it under `tests/spec/`
  **and** wire it into `tests/spec/mod.rs`.
- Use `noyalib::from_str` (or the specific loader under test) directly;
  keep the assertion small — one input, one expected value.

### 4.3 Doctest

- Every public item ships a `# Examples` block. `CONTRIBUTING.md:116`
  makes this explicit.
- For fallible APIs also add `# Errors`.
- **Errors-parse-a-repro pattern:** a doctest that demonstrates an
  error variant must parse an actual reproducer YAML, not just
  construct the variant. Exemplar (`src/error.rs:504–508`):

  ```rust
  /// ```
  /// use noyalib::{Error, Value, from_str};
  /// let err = from_str::<Value>("1: a\n\"1\": b\n").unwrap_err();
  /// assert!(matches!(err, Error::KeyCollision(_)));
  /// ```
  ```

  Constructing `Error::KeyCollision("1".into())` on its own is
  allowed only as a supplementary shape-example; the *behaviour*
  demonstration must parse.

### 4.4 Property test

- Add to `tests/proptest.rs` (or a new `properties_<area>.rs`).
- The universal property must be readable in one sentence
  (`parse(emit(v)) == v`, `parse(format(s))` is total, etc.).
- Shrink to minimal counterexamples; commit those as a fixed regression
  test in the nearest topical `tests/*.rs` file.

### 4.5 Fuzz-discovered regression

- Add the minimised crashing input to
  `tests/scanner_panic_regressions.rs` (or the appropriate
  `*_panic_regressions.rs`) — one `#[test]` per input.
- Keep the raw corpus entry under `fuzz/corpus/<target>/` so the
  fuzzer will not re-discover it.

---

## 5. Acceptance thresholds

Before you claim "ready to merge":

| Gate                           | Threshold                                    | Where enforced                                 |
|--------------------------------|----------------------------------------------|-----------------------------------------------|
| Official YAML Test Suite       | `compliance >= 94.0` assertion; `SKIP_LIST = &[]` so total-loaded pass count must not drop | `tests/official_suite.rs:295–314` + review |
| Coverage — functions           | Target 98% / current gate **96%**            | `--fail-under-functions 96` (`ci.yml:160` + `shared-coverage.yml` default) |
| Coverage — lines               | Target 98% / current gate **94%**            | `--fail-under-lines 94` (`ci.yml:161` + `shared-coverage.yml` default) |
| Coverage — regions             | Target 98% / current gate **93%**            | `--fail-under-regions 93` (`ci.yml:162` + `shared-coverage.yml` default) |
| Clippy                         | `-D warnings` — zero warnings                | Workspace CI                                   |
| Rustfmt                        | Clean (`make fmt`)                           | Workspace CI                                   |
| Doctests                       | All ~480 pass (`cargo test --doc`)           | Workspace CI                                   |
| REUSE / SPDX                   | Every source file carries a header           | REUSE workflow                                 |
| Miri                           | Focused pass green per PR                    | Miri workflow                                  |
| Fuzz smoke                     | Differential fuzz 10s per target             | `Differential fuzz` workflow                   |

The 98/98/98 target is the live campaign — see
`noyalib-coverage-campaign` for the plan to lift the live gate
(96/94/93 functions/lines/regions) up to 98/98/98. `doc/TESTING.md`
still cites `95 / 93 / 92`; that is documentation drift — trust
the workflow files. A conformance regression (any yaml-test-suite
case dropping from pass to fail/skip) is a **release blocker**,
not a "next PR" item.

---

## 6. What does NOT count as evidence

Explicitly rejected. If any of the below is your entire justification,
the PR is not ready:

1. **"It looks right."** — reading the diff is not testing.
2. **A passing test with no failing-before counterpart.** — the test
   must be shown (locally or via reviewer's mental replay of the diff)
   to fail on the pre-fix tree.
3. **Coverage-only tests that execute but do not assert.** — every
   `#[test]` asserts something an engineer can read. A test that
   only calls `from_str` and drops the result is not a test; wrap
   it with `assert!(matches!(...))` or `assert_eq!` on a value.
   The `coverage_*` family is not exempt from this rule.
4. **Bench deltas within noise.** — Criterion prints a p-value; if
   the CI comparison harness (CodSpeed) does not flag the delta as
   significant, it is not a regression *and* it is not an
   improvement. Do not claim either.
5. **"Green on my machine."** — full CI must be green. See the
   CI-always-green invariant.
6. **A doctest that only constructs a type.** — for behavioural
   claims, parse a reproducer (see §4.3).

---

## 7. When NOT to use this skill

- You need to *run* the tests or interpret llvm-cov output →
  `noyalib-diagnostics-and-tooling`.
- You are working the 95 → 98 coverage push specifically →
  `noyalib-coverage-campaign`.
- You are researching whether a bug was fixed before →
  `noyalib-failure-archaeology`.
- You are deciding *what* to build → `noyalib-architecture-contract`.

---

## Provenance

The read-only re-verification one-liners (test-file count, SPDX
coverage, suite case count, the coded `compliance >=` floor, doctest
count, wired coverage thresholds, fixture inventory) live in
`reference.md` §R3. Run them before quoting any number here.

**Date-stamp:** 2026-07-07 · **Crate version:** v0.0.14 · **Ground
truth:** `crates/noyalib/tests/`, `doc/TESTING.md`, `CONTRIBUTING.md`,
`Makefile`.
