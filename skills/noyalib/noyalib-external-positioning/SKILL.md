---
name: noyalib-external-positioning
description: |
  Guides how noyalib is described to the outside world — the ecosystem map,
  provable differentiators, claiming rules, reproducibility standards, and the
  serde_yaml refugee migration playbook. Load this when writing or reviewing
  README claims, release notes / RELEASE-NOTES-*.md, marketing / launch copy,
  blog posts, conference abstracts, papers, competitor / peer comparisons,
  migration guides (MIGRATION-FROM-*.md), the COMPARISON.md matrix, benchmark
  headlines, "why noyalib vs X", "is noyalib faster than X", "what makes
  noyalib different", "how does noyalib compare to serde_yaml / serde_yaml_ng /
  serde_yml / serde-norway / serde-yaml-bw / saphyr / serde-saphyr /
  yaml-spanned / yaml-rust2 / libyaml-safer", or any question about what we
  can and cannot claim in public. Ecosystem cells drift fast: everything is
  date-stamped 2026-07-08 and must be re-verified before publication.
---

# noyalib external positioning

**Scope.** Everything the project says about itself in public — READMEs,
release notes, MIGRATION-FROM-*.md, COMPARISON.md, BENCHMARKS.md, blog
posts, papers, tweets, conference talks. Load before touching any of that
surface. For internal docs (USER-GUIDE, ARCHITECTURE, POLICIES) load
`noyalib-docs-and-writing`. For unproven / speculative directions load
`noyalib-research-frontier`.

**Snapshot date: 2026-07-08.** The ecosystem below drifts. Re-verify
before shipping copy that names a peer.

---

## 1. Ground truth (read before making a claim)

- `doc/COMPARISON.md` — the ecosystem matrix. Cell states dated **2026-05**
  in-file; re-check crates.io + each repo before publication.
- `doc/BENCHMARKS.md` — headline speedups, methodology, hardware
  disclosure (Apple M4, aarch64-apple-darwin, Rust 1.95 stable, criterion
  `--warm-up-time 2 --measurement-time 4`, `--release` LTO=fat cgu=1
  panic=abort). Reproducible via `cargo bench --bench comparison`.
- `README.md` — user-facing top-of-funnel claims; the "One-minute
  migration" table lists every peer we court.
- `doc/MIGRATION-FROM-*.md` — per-crate function tables (serde_yaml,
  serde_yaml_ng, serde_yml, serde-norway, serde-yaml-bw, serde-saphyr,
  yaml-serde, yaml-spanned).
- `crates/noyalib/benches/comparison.rs` — the benched peers today are
  `serde_yaml_ng`, `yaml-rust2`. `serde_yml` / `libyml` were dropped in
  v0.0.6 over RUSTSEC-2025-0067 + RUSTSEC-2025-0068
  (`doc/POLICIES.md` §3, CHANGELOG under v0.0.6).
- `crates/noyalib/tests/competitive_features.rs`,
  `competitive_features_full.rs`, `competitor_bugs.rs` — parity tests +
  reproductions of upstream bugs (e.g. yaml-rust2#70 UTF-8 flow).
- `crates/noyalib/src/de/config.rs` — the current authoritative list of
  `ParserConfig::max_*` builder methods (do not repeat a hand-typed
  budget count — grep the source).

---

## 2. Ecosystem map (2026-07 — verify each row before publication)

Give every peer its honest claim to fame, then noyalib's honest
differential. No disparagement — verifiable facts only.

- **`serde_yaml` (dtolnay/serde-yaml)** — the historical default; archived
  by its maintainer in 2024. This is the migration wave noyalib courts.
  Shim: `compat-serde-yaml` feature; guide:
  `doc/MIGRATION-FROM-SERDE-YAML.md`. State: "unmaintained since 2024,"
  not "abandoned" / "dead."

- **`serde_yaml_ng`** — active community fork of serde-yaml; the current
  de-facto ecosystem successor and the primary head-to-head bench peer
  in `benches/comparison.rs`. Guide:
  `doc/MIGRATION-FROM-SERDE-YAML-NG.md`. Wraps `libyaml` via
  `unsafe-libyaml` (verify via `cargo tree`).

- **`serde-norway`** — another serde-yaml fork under different governance.
  Migration guide: `doc/MIGRATION-FROM-SERDE-NORWAY.md`. Not currently a
  bench peer (add before claiming perf parity/superiority against it).

- **`serde-yaml-bw`** — another serde-yaml lineage crate. Guide:
  `doc/MIGRATION-FROM-SERDE-YAML-BW.md`.

- **`serde_yml`** — a prior serde-yaml derivative; **retired from bench
  dev-deps in v0.0.6** because of RUSTSEC-2025-0067 + RUSTSEC-2025-0068
  in `libyml`. State only the verifiable fact ("dropped from bench
  dev-deps to close the OpenSSF Scorecard Vulnerabilities check after
  RUSTSEC-2025-0067 / -0068 landed"). No adjectives. See
  `doc/POLICIES.md:260` and CHANGELOG v0.0.6.

- **`saphyr` / `serde-saphyr`** — conformance-focused pure-Rust peer
  ecosystem. **saphyr is also a noyalib dependency** (opt-in
  `serde-saphyr` feature — differential-testing / reference-parser
  fallback). Do not frame as an adversary. `serde-saphyr` is a benched
  peer in BENCHMARKS.md headline. Guide:
  `doc/MIGRATION-FROM-SERDE-SAPHYR.md`.

- **`yaml-spanned`** — the closest other span-tracking parser. Benched in
  BENCHMARKS.md headline. Guide: `doc/MIGRATION-FROM-YAML-SPANNED.md`.

- **`yaml-rust2`** — the heaviest-tuned non-serde parser; the perf floor
  noyalib benches against. Also the source of `competitor_bugs.rs`
  reproductions (yaml-rust2#70 etc.). No serde integration, so not a
  drop-in refugee target.

- **`libyaml-safer`** — pure-Rust translation of libyaml. Included in the
  ecosystem context; not currently a bench peer or a migration target we
  publish a guide for.

- **`yaml-serde`** — covered by `doc/MIGRATION-FROM-YAML-SERDE.md`.

**Rule:** before naming any peer in copy, `cargo search <peer>` +
open the repo. If the last release was in the last 90 days, re-check
their README's own claims — they may have shipped a feature that
invalidates a "unique to noyalib" line.

---

## 3. Provable differentiators (each with WHERE the proof lives)

Everything here is CI-enforced or bench-reproducible. If you cannot
point at a file, remove the claim.

- **Zero `unsafe` (workspace-wide).** `#![forbid(unsafe_code)]` at
  every crate root (see `crates/noyalib/src/lib.rs`) plus
  `unsafe_code = "forbid"` in the `[lints.rust]` table of
  `crates/noyalib/Cargo.toml`. Enforcement is at the rustc /
  Cargo-lint layer, not a `cargo geiger` job — no such job exists
  in `.github/workflows/`. Proof: `grep -R "unsafe" crates/`
  returns zero blocks in first-party code. Peers with C-FFI
  (`serde_yaml_ng`, `serde_yml`) fail this via `unsafe-libyaml` in
  the tree — verify via `cargo tree`.

- **Spans + `Spanned<T>`.** Every deserialized field can carry
  `(line, column, byte_offset)` and serialize transparently as `T`.
  COMPARISON.md marks this yes/no across the matrix; re-verify against
  `yaml-spanned` and `saphyr` before writing "unique among serde-YAML
  crates" — both have span support in some form. The current honest
  framing is: "spans **with a `serde`-typed `Spanned<T>` wrapper that is
  transparent to the serde surface**."

- **Lossless CST editing (the moat).** `noyalib::cst::Document` +
  `set(path, value)` — span-precise edits that preserve original
  formatting (comments, blank lines, indent style). No peer in
  COMPARISON.md ships this. Proof: the CST module, the recent
  span-fidelity commits (see recent CHANGELOG entries around alias
  span-through, block-collection value spans, keep-chomped scalars).

- **DoS budget suite.** `ParserConfig` exposes a suite of `max_*`
  builders. Do not hard-code a count in copy — grep source of truth:
  `grep -c "pub fn max_" crates/noyalib/src/de/config.rs`. Current
  builders include `max_depth`, `max_document_length`,
  `max_alias_expansions`, `max_mapping_keys`, `max_sequence_length`,
  `max_events`, `max_nodes`, `max_total_scalar_bytes`, `max_documents`,
  `max_merge_keys`, plus `max_include_depth`. README §"Configurable
  resource budgets" lists the default vs `strict()` values. Peer
  comparisons: COMPARISON.md marks `serde_yml`/`serde_yaml_ng` as
  "Basic", `saphyr`/`rust-yaml` as "Yes", `yaml-rust2` as "No" —
  state peers' posture only if COMPARISON.md still says so.

- **Official-suite conformance.** Ground truth lives in the tests:
  `crates/noyalib/tests/official_suite.rs` sets
  `SKIP_LIST = &[]` (line 164) and asserts
  `compliance >= 94.0` (line 312); `yaml_compliance_report.rs`
  mirrors the empty skip list. 351 wrapper `.yaml` files under
  `tests/yaml-test-suite/` unpack to a larger number of case
  documents. Prose in `README.md` ("387/387, 19 skipped") and
  `doc/BENCHMARKS.md` ("406/406, 0 skipped") disagrees with the
  tests — that is in-tree documentation drift. Cite the tests, not
  the prose: "no skip list, ≥94 % compliance floor, empty
  `SKIP_LIST` asserted". Re-run before releasing any specific
  pass-count claim. The other libraries either don't track this
  publicly or apply lenience.

- **Supply-chain posture.** SLSA L3 provenance, sigstore keyless signing,
  `cargo-deny` / `cargo-vet` / `cargo-semver-checks` gates, REUSE.software
  3.3 compliance, signed commits, OpenSSF Scorecard **~9/10 (was 6.5
  before v0.0.6)** — see `doc/POLICIES.md` §3. Every artifact carries a
  cosign keyless signature + SLSA L3 attestation. `noyalib` currently
  targets the OpenSSF Best Practices Badge for the v0.1 milestone (not
  yet earned — do not claim it).

---

## 4. Claiming rules (project law)

These are non-negotiable. Break one and the release notes have to be
retracted.

1. **No performance claim without a criterion run in the same PR.**
   Hardware, toolchain, and flags disclosed exactly the way
   `doc/BENCHMARKS.md` opens: chip, target triple, Rust version,
   criterion flags, `--release` + LTO / codegen-units / panic settings.
   "Fast" / "high-performance" are fine as flavour text; any *number*
   needs a reproducible bench.

2. **No "faster than X" without a runnable comparison.** The comparison
   bench (`benches/comparison.rs`) must include X *in the same PR* that
   ships the copy. Third parties must be able to reproduce with a single
   `cargo bench --bench comparison`. Peers dropped from bench dev-deps
   (currently `serde_yml`, `libyml`) cannot appear in perf copy without
   being re-added and the RUSTSEC exposure re-evaluated.

3. **No uniqueness claim without checking current peer versions.** Peers
   evolve. "Only Rust YAML library that does X" ages fast. Re-verify
   against the last crates.io release of every peer named in
   COMPARISON.md before shipping the claim. If in doubt, downgrade to
   "the only [category] we know of" or "unique among the peers in
   COMPARISON.md as of 2026-07-08."

4. **Unproven = labeled candidate/open.** If it isn't measured or
   CI-enforced, the copy says "candidate", "planned", "roadmap", or
   "goal" — never a bare present-tense assertion. Load
   `noyalib-research-frontier` for the speculative bucket.

5. **Security claims only for what CI enforces.** "Zero unsafe" is
   fine because `#![forbid(unsafe_code)]` gates it. "DoS-safe" is fine
   because the budget suite is on by default and the strict mode is
   documented. "Memory-safe" without a Miri run in CI is *not* fine.
   "Constant-time" claims require a `dudect` / `cachegrind` measurement,
   which we do not currently ship.

6. **No disparagement.** State only verifiable facts about peers. The
   RUSTSEC-2025-0067/-0068 note about `libyml` is a *fact*; framing it
   as a value judgement about the maintainer is not. Ecosystem
   goodwill is a project asset.

---

## 5. Reproducibility standards

Everything measured must be re-runnable by a third party from a
freshly-cloned repo with a single command. Copy the pattern already
in `doc/BENCHMARKS.md`:

- **Hardware disclosure.** Chip, architecture triple, OS revision.
- **Toolchain disclosure.** Exact Rust version (currently 1.95 stable).
- **Build flags.** `--release`, LTO=fat, codegen-units=1, panic=abort.
  If PGO was used (`cargo xtask pgo-build`), say so and note the +5–15%
  headroom on top of the un-PGO numbers.
- **Criterion knobs.** `--warm-up-time 2 --measurement-time 4` unless
  stated otherwise.
- **Fixture provenance.** Point at the file
  (`crates/noyalib/benches/fixtures/*.yaml`) so readers can inspect
  the exact input.
- **Reproducible-builds ambition.** PLAN.md Phase 7 tracks byte-for-byte
  reproducibility as a 1.0 gate. Third-party verification is part of
  that gate — do not claim "reproducible builds" as shipped yet; do
  claim "reproducible-builds work is on the 1.0 gate list."
- **Signed provenance on every artifact.** cosign keyless + SLSA L3.

For CST / semantic claims (span accuracy, format preservation),
reproducibility means the round-trip test: parse → CST → serialize
back to bytes-equal-input on the fixture set. If it isn't in the
test suite, the claim is not shippable.

---

## 6. Migration-audience playbook

The migration wave is the primary v0.0.x audience. The pitch order
matters.

- **Lead with the drop-in surface.** The `compat-serde-yaml` feature
  provides `noyalib::compat::serde_yaml` re-exports backed by
  noyalib-native types. The unmaintained `serde_yaml` 0.9 crate is
  intentionally **not** a dependency — the shim is a re-export layer,
  not a re-export of the abandoned crate. Migrating in-flight
  `::serde_yaml::Value` from un-migrated modules routes through
  `noyalib::to_value(&upstream)?`.

- **Then the per-crate guide.** `doc/MIGRATION-FROM-*.md` — each is a
  function-mapping table + behavioural-difference notes + checklist.
  All eight (serde_yaml, serde_yaml_ng, serde_yml, serde-norway,
  serde-yaml-bw, serde-saphyr, yaml-serde, yaml-spanned) live in
  `doc/`; the umbrella index is `doc/MIGRATION.md`.

- **Then the upgrades.** In this order, matching what a `serde_yaml`
  refugee cares about:
  1. **Correctness.** 100% strict on the YAML 1.2 official Test Suite;
     `competitor_bugs.rs` reproductions.
  2. **Security.** DoS budget suite + `ParserConfig::strict()`,
     billion-laughs coverage, zero `unsafe`.
  3. **Spans.** `Spanned<T>` for pinpoint diagnostics when config files
     go wrong.
  4. **CST / editing.** Lossless format-preserving edits — for tools
     that mutate user config files.
  5. **Performance.** The numbers, with methodology attached.

- **The upgrade order matters** because the refugee's default fear is
  "will my existing code break?" (answered by the shim), not "is this
  faster?" (which is the fifth question, not the first).

---

## 7. When NOT to use this skill

- Writing the docs themselves (USER-GUIDE.md, ARCHITECTURE.md,
  POLICIES.md, per-module docstrings) → load `noyalib-docs-and-writing`.
- Research / speculative directions not yet measured or CI-enforced →
  load `noyalib-research-frontier`.
- Architecture invariants of the library itself → load
  `noyalib-architecture-contract`.
- Changing CI / release plumbing → load `noyalib-ci-and-release`.

---

## 8. Provenance / re-verification checklist

Before merging any copy that names a peer, benchmarks a peer, or makes
a uniqueness claim, run:

```bash
# Ecosystem matrix (verify header date; cells claim 2026-05 truth)
head -40 doc/COMPARISON.md

# Benchmark methodology + headline numbers
head -80 doc/BENCHMARKS.md

# Current benched peers
grep -n "^use\|serde_yaml_ng\|yaml_rust2\|serde_yml\|yaml_spanned\|serde_saphyr" \
  crates/noyalib/benches/comparison.rs | head -20

# Retired peers + rationale
grep -n "RUSTSEC-2025-006\|serde_yml\|libyml" CHANGELOG.md doc/POLICIES.md

# Current budget builders (authoritative source)
grep -c "pub fn max_" crates/noyalib/src/de/config.rs

# Peer freshness: is COMPARISON.md still current?
cargo search serde_yaml_ng serde-norway serde-yaml-bw serde_yml \
  saphyr serde-saphyr yaml-spanned yaml-rust2 libyaml-safer
```

If any of the above surfaces a discrepancy with the copy under review,
the copy is stale — fix it or drop the claim.

Snapshot date on this skill: **2026-07-08**. Anything in this file
that names a peer version, a number, or a "unique" claim is by
definition volatile. Re-verify before publication.
