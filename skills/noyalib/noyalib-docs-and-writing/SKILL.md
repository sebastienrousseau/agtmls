---
name: noyalib-docs-and-writing
description: Maintain noyalib's docs of record and house writing style. Use when authoring or editing README, CHANGELOG, RELEASE-NOTES-vX.Y.Z.md, ADRs under doc/adr/, doc/POLICIES.md, doc/ARCHITECTURE.md, doc/USER-GUIDE.md, GLOSSARY.md, MIGRATION*.md, GETTING_STARTED.md, or crate-level and item-level rustdoc. Covers house rustdoc style (# Examples, # Errors, runnable doctests), commit-message archaeology (Assisted-by trailer, symptom/root-cause bodies), SPDX/REUSE headers per file type, ADR lifecycle (when required, template, post-implementation updates), release-notes template, and the version-refs release audit. Do NOT use for release mechanics (see noyalib-ci-and-release) or competitive positioning (see noyalib-external-positioning).
---

<!-- SPDX-FileCopyrightText: 2026 Noyalib -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->

# noyalib-docs-and-writing

House style and process for noyalib's documentation of record.
Repo is v0.0.14 (2026-07-07) on the `feat/v0.0.14` branch, on the
0.0.x runway toward v0.1.0. Skill date-stamp: **2026-07-08**.

> **Reference material** (the verbatim per-file-type SPDX header
> shapes, the full ADR process + skeleton, and the release-notes
> template): see `reference.md` in this directory. This file keeps the
> docs-of-record inventory, rustdoc / commit-message house style, the
> writing rules, and the pre-PR self-check.

## Provenance checks

Run before authoring to confirm shape hasn't drifted:

```sh
head -20 CHANGELOG.md                        # Keep-a-Changelog shape
ls doc/adr/                                  # ADR inventory + numbering
ls RELEASE-NOTES-v*.md | tail -5             # release-notes cadence
head -3 crates/noyalib/src/de.rs             # .rs SPDX header shape
head -2 RELEASE-NOTES-v0.0.14.md             # .md SPDX header shape
head -2 .github/workflows/shared-no-std.yml  # .yml SPDX header shape
git log -5 --format='%s%n%b%n---'            # commit-body archaeology
grep -n 'missing_docs' crates/noyalib/src/lib.rs
```

## Docs of record — inventory

Every claim in these files is load-bearing. Update in the same PR
as the behaviour change, never as a follow-up.

- **`README.md`** — public promises: install, quick start,
  capabilities, ecosystem, comparison, benchmarks, features,
  when-not-to-use. Every claim must stay true.
- **`CHANGELOG.md`** — Keep a Changelog 1.1.0. `[Unreleased]`
  rolling section on top, then descending version sections. Each
  version records lockstep-satellite bumps and links
  (`noyalib-wasm`, `noyalib-mcp`, `noyalib-lsp`, `noya-cli`).
- **`RELEASE-NOTES-vX.Y.Z.md`** — per-release narrative, one file
  per release, SPDX headers inline. Template extracted below from
  `v0.0.14` and `v0.0.13`.
- **`doc/POLICIES.md`** — engineering law: zero-`unsafe`, MSRV,
  `#![forbid(unsafe_code)]`, security posture, DoS-budget defaults.
  Cite before writing any PR risking an invariant.
- **`doc/ARCHITECTURE.md`** — system shape: parser → loader(s) →
  serde / Value / CST, streaming fast-path eligibility, module map.
- **`doc/USER-GUIDE.md`** — task-oriented, with feature-gated
  Cargo.toml snippets (recovery, tokio, sval, …). Version-locked
  snippets appear here.
- **`GLOSSARY.md`** — precise vocabulary (CST, span, alias, merge
  key, chomping, DoS budget). Link liberally from other docs.
- **`MIGRATION.md`** (root) — cross-release migration for downstream
  vendors and pinning consumers.
- **`doc/MIGRATION-FROM-*.md`** — per-competitor playbooks
  (serde-yaml, serde-yaml-ng, serde-yaml-bw, serde-norway,
  serde-saphyr, serde-yml, yaml-serde, yaml-spanned).
- **`doc/adr/NNNN-*.md`** — Architecture Decision Records.
  Immutable once accepted. See ADR process below.
- **`GETTING_STARTED.md`** — 5-minute walkthrough; version-refs
  live here and must be audited on release.
- **Reference material** — `doc/COMPARISON.md`, `doc/BENCHMARKS.md`,
  `doc/PGO.md`, `doc/TESTING.md`, `doc/CII-BEST-PRACTICES.md`,
  `doc/pre-commit.md`. Date-stamp anything volatile.
- **Community posture** — `CONTRIBUTING.md`, `SECURITY.md`,
  `SUPPORT.md`, `GOVERNANCE.md`, `CODE_OF_CONDUCT.md`. Rare touch.

## Rustdoc house style

Lint is `#![warn(missing_docs)]` at `crates/noyalib/src/lib.rs:343`.
Every public item is documented. The ~480 doctests under
`cargo test -p noyalib` are load-bearing — treat regressions as
test failures.

Rules (extracted from `crates/noyalib/src/de.rs`,
`crates/noyalib/src/ser.rs`, `crates/noyalib/src/lib.rs`):

1. **Lead one-line summary.** Verb-first, no hedging.
2. **Long-form paragraph explains *why* / *how it routes*.**
   Fast-path eligibility, defaults, coupling to nearby types.
3. **`# Examples` with runnable doctests.** Prefer runnable over
   `ignore` / `no_run`. `no_run` is acceptable only for I/O,
   panics, or long-running examples.
4. **`# Errors` on every fallible fn.** Enumerate `Error::Variant
   — cause` bullets. Cross-link the `ParserConfig` field for DoS
   budgets.
5. **Error-demonstrating doctests parse a reproducer** rather than
   merely constructing the variant. A `KeyCollision` doctest
   includes the two-key YAML that triggers it.
6. **Module-level `//!` docs explain WHY, not just what.** See
   `crates/noyalib/src/lib.rs` for the tone: "Two APIs, one
   parser", "Pure Rust — native YAML 1.2 scanner and parser."
7. **Comments carry incident context.** When a subtle fix lands,
   capture the trap next to the code, not just in the commit body.
   Canonical in-tree examples:
   - `.github/workflows/shared-no-std.yml` lines 12-14 — scoped
     `CARGO_TARGET_DIR` prose explains why the default `target/`
     under Swatinem cache poisons the no_std fingerprint.
   - `crates/noyalib/src/streaming.rs` `raw_str_mode` field
     (around line 78 / 142) — why the flag exists on the
     streaming path.

Formatting: backticks around every identifier, path, feature, or
CLI flag. Intra-doc links via `[`Foo`](crate::Foo)`. Wrap ~72
columns. No emoji.

## Commit-message house style

Commit archaeology is unusually load-bearing here. Each body is a
decision record in miniature.

Structure:

```
<type>(<scope>): <imperative subject, ≤72 chars>

<paragraph 1 — symptom the user or CI observed>

<paragraph 2 — root cause, cited with file paths / line numbers>

<paragraph 3 — the fix, and why this shape over alternatives>

<optional: verification commands and their observed output>

Assisted-by: Claude:<model-id>    (or: Claude <noreply@anthropic.com>)
```

Real subjects from `git log -5`:

- `fix(cst): resolve alias references through to the anchor value span`
- `feat(no_std): core::error::Error + wasm32 CI bare-metal proof`
- `fix(bench): merge_heavy variant needs lifted max_alias_expansions`
- `docs(release): bump straggler 0.0.14 version refs across docs`

Rules:

- **Conventional Commits.** `feat`, `fix`, `perf`, `refactor`,
  `docs`, `test`, `ci`, `chore`. Scope is the touched surface
  (`cst`, `no_std`, `ci`, `release`, `bench`).
- **Body is archaeology.** Symptom → root cause → rationale →
  verification. A memo to the contributor who will hit the same
  class of bug in 2027.
- **Cite specifics.** Files, line numbers, error messages,
  observed numbers. `git blame` should land on prose that
  explains itself.
- **Verification commands + observed output** when the change is
  behavioural. Copy `cargo test` / `cargo bench` lines verbatim.
- **`Assisted-by:` trailer** when a model contributed. Both
  in-tree forms are acceptable.
- **Signed commits.** `git commit -S`.
- **Never `--amend` after a hook failure.** Fix and add a NEW
  commit.

## SPDX / REUSE discipline

REUSE 3.3 — every file is licensed inline or via `REUSE.toml` blanket
annotations, and CI has a REUSE gate. The per-file-type header shapes
(`.rs`, `.yml`/`.yaml`, release-notes `.md`, top-level `.md` blanket,
config/fixture wildcards) are in `reference.md` §R1 — use them
verbatim. Copyright year is the current release year; don't rewrite
history on rollover, only new files get the new year.

## ADR process

ADRs live under `doc/adr/` in Nygard's shape (Context / Decision /
Consequences / Alternatives / References), numbered next-integer
zero-padded to 4 (currently through 0005), immutable once accepted
except for post-implementation pilot-results appends. **Add one** for a
change to the data model, public API, dependency floor, a core
invariant, or parser/loader output — or any decision a future
contributor might propose the opposite of; **skip** it for
type-encoded/idiomatic/routine choices (commit body suffices). The full
when-to / when-not-to, status lifecycle, and the verified skeleton are
in `reference.md` §R2. Update `doc/adr/README.md`'s index after adding
one.

## Release-notes template

One file per release, SPDX headers inline, modelled on `v0.0.14` /
`v0.0.13`: headline + "Why this release exists" + "What changed" +
"What did not change" (fights oversell) + "Follow-ups for vX.Y.(Z+1)",
plus a per-satellite channel section when one ships in the same cut.
Full template in `reference.md` §R3.

## Writing rules

1. **No oversell.** Unproven claims stay labelled `candidate` or
   `open question`, or are omitted. `#![forbid(unsafe_code)]` IS
   proven — cite freely. "Fastest YAML library" is NOT proven
   without a matching bench.
2. **No perf number without a bench in the same PR.** Numbers in
   README must be reproducible from `cargo bench` on a stated
   target. See `benches/parallel.rs` for the "~1.5× locally on
   aarch64" pattern.
3. **Version-refs audit on release.** Before saying "release PR
   is mergeable", grep for stale versions:

   ```sh
   git grep -n 'noyalib.*=.*"0\.0\.' -- \
     README.md MIGRATION.md GETTING_STARTED.md \
     'doc/**/*.md' 'crates/**/README.md' \
     RELEASE-NOTES-*.md CHANGELOG.md
   git grep -n '0\.0\.[0-9]\+' -- benches examples fuzz
   ```

   Recurring failure mode. Commit `7afa2d31`
   (`docs(release): bump straggler 0.0.14 version refs`) surfaced
   stale `0.0.8`/`0.0.11`/`0.0.13` references AFTER the release
   PR was thought mergeable. Do it before, not after.
4. **Date-stamp volatile claims.** Benchmarks, dep counts,
   coverage percentages, published-crate lists, satellite status.
   Use "as of vX.Y.Z (YYYY-MM-DD)" or rotate the number into a
   per-release doc.
5. **Prose voice** matches crate-level rustdoc: direct, verb-first,
   no filler. "noyalib parses YAML 1.2." — not "noyalib is a
   library that provides parsing for the YAML 1.2 format".
6. **Cross-link, don't restate.** README links to
   `doc/POLICIES.md` or the relevant ADR for invariants. One
   source of truth per fact.
7. **Never introduce facts a reader can't verify.** Every claim
   points to a test, bench, config field, doc, ADR, or commit.
8. **No emoji.**

## When NOT to use this skill

- **Release mechanics** (tag cutting, `cargo publish`,
  satellite version cross-check, release workflow debugging) —
  use `noyalib-ci-and-release`.
- **External positioning** (competitor comparisons vs
  serde-yaml/serde-saphyr/libyaml, marketing copy) — use
  `noyalib-external-positioning`.
- Architecture decisions with API implications coordinate with
  the code changes themselves; this skill only covers the
  ADR-writing shape.

## Self-check before opening a docs PR

- [ ] Every new claim has a citation (test, bench, config, ADR,
      or code path).
- [ ] Version refs match the release target across README,
      MIGRATION, GETTING_STARTED, per-crate READMEs, and doc/*.md.
- [ ] SPDX header present or REUSE.toml covers the file.
- [ ] CHANGELOG `[Unreleased]` (or a new version section) captures
      the user-visible change.
- [ ] New public items have one-line summary + `# Examples` +
      `# Errors` (if fallible).
- [ ] New doctests are runnable unless there's a specific reason.
- [ ] Commit body has symptom → root cause → rationale, with
      `Assisted-by` trailer where applicable.
- [ ] Structural / hard-to-reverse change carries a new ADR or a
      post-implementation update to an existing one.
- [ ] No emoji introduced.
