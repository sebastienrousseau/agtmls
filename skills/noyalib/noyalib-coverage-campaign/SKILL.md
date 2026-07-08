---
name: noyalib-coverage-campaign
description: >-
  Executable, decision-gated playbook for the noyalib coverage-hardening
  campaign — driving line/branch/function coverage from the live workspace
  gate (96 fn / 94 lines / 93 regions per .github/workflows/ci.yml and
  shared-coverage.yml defaults; doc/TESTING.md still says 95/93/92 and is
  stale drift) toward the 98 % target declared in PLAN.md. Load this when
  the ask is "raise coverage", "close the llvm-cov gaps", "what should I
  work on next", "make coverage-gap says X is under threshold", "ratchet
  the fail-under numbers", "we're at 96, get us to 98", or any variant of
  coverage triage on this repo. Coordinates the
  scripts/coverage-gap-report.sh punchlist, the tests/coverage_*.rs
  house-pattern, and the shared-coverage.yml gate. Owns the end-to-end
  workflow: baseline → target selection → gap analysis → test authoring →
  verification → promotion. Explicitly fences off wrong turns (chasing
  100 %, weakening thresholds, assert-free coverage tests, testing
  invariant_violated defensive paths).
---

# noyalib-coverage-campaign

**Purpose.** Run the coverage-hardening campaign to specification, unsupervised,
on a Sonnet-class session. This skill is the *decision procedure*, not a
tutorial: at each phase there is a command, an expected observation, and a
gate that says whether to proceed, retry, or escalate.

**Scope guard.** This skill covers only the coverage campaign. For the wider
"how do we test noyalib at all" question (test layers, proptest, fuzz,
Miri, spec suite) use **noyalib-validation-and-qa**. For interpreting a
specific tool's output (llvm-cov flags, cargo-vet, deny) use
**noyalib-diagnostics-and-tooling**. Do not duplicate those skills here.

**Progressive disclosure.** This SKILL.md is the campaign spine. Extended
material — bucket-classification walkthroughs, verbatim house-pattern
snippets, "why not" rationale for each fenced wrong-path, expanded
solution-menu prefer-when notes, and the `invariant_violated`
file:line inventory — is in
[`reference.md`](./reference.md). Load `reference.md` when the compact
guidance below is insufficient; each section flags its
cross-reference.

---

## 0. Baseline numbers (VOLATILE — re-verify at campaign start)

Captured 2026-07-08 from `.github/workflows/ci.yml:160-162`,
`.github/workflows/shared-coverage.yml` reusable defaults,
`doc/TESTING.md` §"Coverage gate", and PLAN.md §1 "Coverage baseline":

| axis      | live workspace gate (`ci.yml`) | shared-coverage.yml default | `doc/TESTING.md` (stale) | target |
|-----------|-------------------------------:|----------------------------:|-------------------------:|-------:|
| functions | 96 %                           | 96 %                        | 95 %                     | 98 %   |
| lines     | 94 %                           | 94 %                        | 93 %                     | 98 %   |
| regions   | 93 %                           | 93 %                        | 92 %                     | 98 %   |

Two threshold layers exist and both must be understood:

1. **Live workspace gate (`.github/workflows/ci.yml:160-162`, 96/94/93)** —
   the values a PR is actually measured against today. This matches the
   `shared-coverage.yml` reusable-workflow defaults; the workspace caller
   does not override them.
2. **`doc/TESTING.md` documented axis (95/93/92)** — documentation drift.
   The doc lags the workflow files by one ratchet step. Trust the workflows;
   fix the doc in the same PR that next moves the gate.

**These numbers drift.** Before touching anything, run Phase 0 and treat
the axis printed there as ground truth. If Phase 0 disagrees with this
table by more than 1 pp on any axis, update this section in the same PR
that closes the gap that caused the drift.

---

## Phase 0 — Baseline: what do we actually cover today?

**Command (canonical):**

```bash
make coverage-gap
# equivalent to:
#   ./scripts/coverage-gap-report.sh          # 98 % threshold (default)
#   ./scripts/coverage-gap-report.sh 95       # ratchet to a custom floor
```

Under the hood this runs (verbatim from `scripts/coverage-gap-report.sh`):

```bash
NOYALIB_COVERAGE=1 cargo +nightly llvm-cov \
    --workspace --all-features --no-fail-fast \
    --ignore-filename-regex '' \
    --summary-only
```

**Expected observation.** A TSV block, header `file  regions  lines  functions`,
one row per file below the threshold, and on stderr a one-liner
`<N> files below <T> %.` The full raw summary is teed to
`/tmp/noyalib-coverage.log`.

**Gate.**

- Zero files below threshold → campaign done for this ratchet step;
  advance to Phase 5 to ratchet the gate numbers.
- N > 0 → continue to Phase 1 with the punchlist.

**If the tool errors:** toolchain mismatch → `cargo +nightly`;
missing nightly → `rustup toolchain install nightly --component
llvm-tools-preview`. Numbers wildly off → confirm `--all-features`.
CI cache poisoning symptom (`cargo check` under 2 s + drifting
numbers) → coverage jobs use `CARGO_TARGET_DIR=target-coverage`
(memory `feedback_ci_cache_poisoning`); locally `cargo clean` and
rerun. Extended error triage in
[`reference.md`](./reference.md) §6.

---

## Phase 1 — Target selection: pick the ≤ 3 files that matter most

**Rule of thumb.** Rank Phase 0 rows by
`(uncovered_lines × load_bearingness)` where load-bearingness is:

| tier | modules                                                             | weight |
|------|---------------------------------------------------------------------|--------|
| S    | `parser/`, `scanner/`, `loader.rs`, `de/`, `ser/`, `error.rs`       | 3      |
| A    | `value.rs`, `borrowed.rs`, `cst/`, `document.rs`                    | 2      |
| B    | `fmt.rs`, `path.rs`, public re-exports                              | 1      |
| C    | convenience wrappers, `Display` shims, example-only helpers         | 0.5    |

Parser / loader / scanner / error paths outrank convenience code, always.
A file at 90 % in `parser/events.rs` beats a file at 85 % in a `Display`
shim (memory `feedback_security_first_posture`: correctness on
adversarial input IS a security control).

**PR discipline gate.** Pick **≤ 3 files per PR**. One logical change
per PR (memories `project_main_branch_protection` +
`feedback_no_premature_phasing`). Bundling five files into one "coverage
sweep" makes the ratchet PR hard to revert per-file if one addition
regresses.

**Entangled files** — e.g. `parser/events.rs` gaps only close when
`scanner.rs` gaps close — may live in the same PR as a single logical
change. Say so in the description.

---

## Phase 2 — Gap analysis: what kind of gap is each uncovered region?

**Command.** For a specific file:

```bash
NOYALIB_COVERAGE=1 cargo +nightly llvm-cov show \
    --workspace --all-features \
    --show-line-counts-or-regions \
    --ignore-filename-regex '' \
    -- crates/noyalib/src/parser/events.rs   # example
```

Or the whole workspace with per-file annotated HTML:

```bash
NOYALIB_COVERAGE=1 cargo +nightly llvm-cov --html --workspace --all-features
open target/llvm-cov/html/index.html
```

**Classification.** Every uncovered region falls into one of four
buckets. This decision drives the rest of the campaign:

| bucket | signal                                                                 | action                                                                                 |
|--------|------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| (a)    | Reachable error path (an `Err(Error::…)` return, a bail on bad input)  | **Write a test** that triggers exactly that input; assert the `ErrorKind` variant.     |
| (b)    | Feature-gated code (`#[cfg(feature = "…")]`, `#[cfg(target_arch = …)]`) | **Feature-matrix test leg** — the workspace's `--all-features` still misses cfg-arch. |
| (c)    | Defensive-unreachable — a `_ =>` arm that calls `invariant_violated`   | **NOT a test target.** Confirm the annotation, document exclusion in PR.               |
| (d)    | Dead code — genuinely unreachable, not defensive                       | **Do not test.** Open a change-control PR to remove it. Coverage rises by subtraction. |

**How to spot (c) vs (d).** (c) is guarded by
`#[cfg_attr(noyalib_coverage, coverage(off))]` and calls
`crate::error::invariant_violated(...)`. If an arm is NOT annotated,
that's the bug — annotate it. (d) is code you can prove no input can
reach; if unsure, write the test first — failure to trigger is
empirical evidence for (d).

Extended walkthroughs (signal / action / common trap per bucket) and
the current `invariant_violated` file:line inventory are in
[`reference.md`](./reference.md) §1 and §3.

---

## Phase 3 — Test authoring: the house pattern

**Location.** `crates/noyalib/tests/coverage_<slug>.rs`. The existing
family is ~20 files including `coverage_scanner.rs`,
`coverage_error.rs`, `coverage_loader{,_full}.rs`,
`coverage_borrowed.rs`, `coverage_ser.rs`, `coverage_de.rs`,
`coverage_fmt.rs`, `coverage_value.rs`,
`coverage_spanned_anchors.rs`, plus historical sweep files
(`coverage_final*.rs`, `coverage_100.rs`, `coverage_remaining.rs`).

**Naming.** Prefer topic-scoped names (`coverage_scanner`) over sweep
names (`coverage_final_sweep4`). Sweep names are historical; don't
add more.

**Every file must:**

1. Start with the SPDX header and a module doc naming the source file
   whose gaps it closes.
2. Assert semantics — every test asserts a specific behaviour, not
   "some output happened". Wrong-but-green is the declared enemy.
3. On error-path tests, `matches!` on the `ErrorKind` variant — not
   `err.to_string()`.

Canonical style references (mirror these three verbatim):
`coverage_scanner.rs`, `coverage_error.rs`, `coverage_loader_full.rs`.
Verbatim snippets (SPDX header, error-path shape, anti-pattern,
"any outcome is fine" exception) are in
[`reference.md`](./reference.md) §2.

**Doctest option.** If the file being covered has a public API without
a `# Examples` section, a doctest closes the coverage gap AND satisfies
the rustdoc-coverage goal in PLAN.md §1 (`missing_docs = warn` → `deny`,
≥ 98 % items). Double win; prefer this on the public surface.

---

## Phase 4 — Verification gate

**Command.** Re-run Phase 0:

```bash
make coverage-gap
```

**Expected.** Targeted files no longer appear in the punchlist, or
appear with all three axes ≥ 98 %. Workspace totals rise by the
uncovered-region contribution of the files closed.

**Gate.**

- Targeted files ≥ 98 on all three axes → proceed to Phase 5.
- Improved but still below 98 → back to Phase 2 for the residual
  regions. Common cause: an error path with three variants, test hit
  two.
- Unchanged → the test isn't actually executing the intended path.
  `dbg!` on entry, run `cargo test --test coverage_<slug> -- <name>
  --nocapture` under `NOYALIB_COVERAGE=1`, confirm the region enters.

**If a file refuses to close the last percent:** check for
`#[cfg(target_arch = …)]` (cross-target is out of scope per PLAN.md
§7.8), macro-expanded lines (`llvm-cov show` quirk on `macro_rules!`;
document as at-ceiling), or `#[cfg]`-conditional match arms needing
a different feature subset (`--no-default-features --features alloc`
for the `no_std` leg — only worth it for tier-S). Extended notes in
[`reference.md`](./reference.md) §6.

**Principled exclusion.** If a region is genuinely (c) or (d) but
cannot be excluded via `#[cfg_attr(noyalib_coverage, coverage(off))]`,
document location + reason in the PR — change-control question, see
**noyalib-change-control**.

---

## Phase 5 — Promotion: normal change control

Standard flow, per memory `project_main_branch_protection`:

1. Branch from `main`, feature branch.
2. Local run of the full pre-push gate (see **noyalib-build-and-env**
   or **noyalib-ci-and-release** for the exact command list).
3. PR into `main` — `main` rejects direct pushes.
4. Wait for CI green on all shared workflows including the coverage
   gate (memory `feedback_ci_must_be_green`).
5. `gh pr merge --squash --admin` once green.
6. If the campaign has fully closed a threshold step (e.g. all files
   ≥ 98 % lines), a *separate* PR ratchets the numbers in **both**:
   - `doc/TESTING.md` §"Coverage gate"
   - the workspace's caller of `shared-coverage.yml` (its
     `fail-under-*` inputs)
   - and, if this is the reference for satellites, the defaults in
     `.github/workflows/shared-coverage.yml`
   Never bundle a threshold ratchet with a test-authoring PR — two
   separate logical changes, different risk profiles.

**Success is measured, not eyeballed.** The number of record is the
`coverage-gate` job (currently 96 fn / 94 lines / 93 regions per
`ci.yml:160-162` + `shared-coverage.yml` defaults), not a local
terminal readout. If CI says "failed under 94 lines" and local says
"94.02", CI wins — check `CARGO_TARGET_DIR` isolation and re-run.

---

## Known wrong paths (fenced — terse list)

Per-item "why not" rationale is in [`reference.md`](./reference.md) §4.

- **Chasing 100 %.** Unreachable by construction; ceiling is ≥ 98 %.
- **Weakening thresholds to pass.** Never lower a `fail-under-*` in
  `shared-coverage.yml` or `doc/TESTING.md` to green a red PR.
- **Assert-free coverage tests.** Wrong-but-green is the declared enemy.
- **Duplicating existing coverage under a new name.** Grep the
  `coverage_*.rs` family first; extend if it exists.
- **Testing `invariant_violated` arms directly.** Annotate them; do
  not reach them via `unsafe` or hand-forged inputs.
- **Touching `${1:-98}` in `scripts/coverage-gap-report.sh` silently.**
  It's contract with the maintainer.
- **Bundling with unrelated refactors.** Two logical changes = two
  PRs. Coverage PRs must be trivially revertible per-file.

---

## The solution menu (ranked — brief)

Given a specific gap, prefer higher-ranked techniques first. Extended
when-to-prefer rationale in [`reference.md`](./reference.md) §5.

1. **Targeted unit / integration test** — default. Use for (a)
   reachable-error-path gaps and single-function invariants.
2. **Proptest generator** — for combinatorial / shape-family gaps
   (scalar shapes × chomping × indent; escape sequences; type tags).
3. **Doctest** on the public API — closes coverage AND moves rustdoc
   coverage toward PLAN.md §1 in one commit.
4. **Fixture-driven spec test** — YAML file under `tests/fixtures/`
   plus expected event stream / value. For YAML-*semantic* gaps
   (anchor/alias corners, merge-key ordering, spec-clause edges).

None replaces the others — a well-covered file uses all four.

---

## Provenance

- **`scripts/coverage-gap-report.sh`** — exact `cargo +nightly llvm-cov`
  invocation, TSV output, default threshold 98 %.
- **`.github/workflows/ci.yml:160-162`** — live `coverage-gate` inputs:
  96 fn / 94 lines / 93 regions.
- **`.github/workflows/shared-coverage.yml`** — reusable workflow.
  Defaults 96/94/93 (caller doesn't override).
  `CARGO_TARGET_DIR: target-coverage` isolation is load-bearing
  (memory `feedback_ci_cache_poisoning`).
- **`doc/TESTING.md` §"Coverage gate"** — stale (95/93/92); trust the
  workflows. Also lists legitimate exclusions
  (`noyalib-wasm/src/lib.rs`, MCP/LSP `protocol.rs`).
- **`PLAN.md` §1 + §7.8** — 98 % target, ratchet plan, cross-target
  matrix as future work.
- **`crates/noyalib/tests/coverage_*.rs`** — ~20-file house pattern.
  Style refs: `coverage_scanner.rs`, `coverage_error.rs`,
  `coverage_loader_full.rs`.
- **`crates/noyalib/src/error.rs::invariant_violated`** (line 1697) —
  the `#[cfg_attr(noyalib_coverage, coverage(off))]` mechanism. Full
  call-site inventory in [`reference.md`](./reference.md) §3.
- **Makefile `coverage-gap` target** — canonical entry point.

Sibling skills (out of scope; delegate):

- **noyalib-validation-and-qa** — proptest / fuzz / Miri / spec-suite.
- **noyalib-diagnostics-and-tooling** — llvm-cov flags, cargo-vet / deny.
- **noyalib-change-control** — ratchet-PR mechanics.
- **noyalib-ci-and-release** — pre-push gate; shared-workflow
  caller-permission unioning (memory `feedback_shared_workflow_caller_perms`).
