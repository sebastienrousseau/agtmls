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

> **Reference material** (the per-peer ecosystem map, the
> reproducibility standards, the migration-audience playbook, and the
> pre-publication provenance checklist): see `reference.md` in this
> directory. This file keeps the ground-truth file list, the provable
> differentiators, and the claiming rules (project law).

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
differential — verifiable facts only, no disparagement. The migration
wave noyalib courts is the `serde_yaml` (archived 2024) refugees;
`serde_yaml_ng` (libyaml-backed) is the primary bench peer;
`saphyr`/`serde-saphyr` and `yaml-spanned` are benched peers (saphyr is
also an opt-in noyalib dep — not an adversary); `serde_yml` was retired
from bench dev-deps in v0.0.6 over RUSTSEC-2025-0067/-0068. Full
per-peer map with each migration guide in `reference.md` §R1.

**Rule:** before naming any peer in copy, `cargo search <peer>` + open
the repo; a release in the last 90 days may invalidate a "unique to
noyalib" line.

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

Every measured claim must be re-runnable by a third party from a fresh
clone with one command, disclosing hardware, exact toolchain, build
flags (`--release` LTO=fat cgu=1 panic=abort), and criterion knobs —
the pattern `doc/BENCHMARKS.md` opens with. Reproducible builds are a
1.0 gate, not shipped — claim the goal, not the fact. Full standard
(the disclosure checklist + the CST round-trip reproducibility rule) in
`reference.md` §R2.

---

## 6. Migration-audience playbook

The migration wave is the primary v0.0.x audience; pitch order is
**drop-in shim → per-crate guide → upgrades**, and the upgrades land in
the order a `serde_yaml` refugee cares about (correctness → security →
spans → CST editing → performance), because "will my code break?" is
the first fear and "is it faster?" the last. Full playbook (shim
mechanics, the eight `MIGRATION-FROM-*.md` guides, ordered rationale)
in `reference.md` §R3.

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

The pre-publication re-verify one-liners (COMPARISON.md header date,
BENCHMARKS.md methodology, current benched peers, retired-peer
rationale, live budget-builder count, peer freshness via `cargo
search`) live in `reference.md` §R4. Run them before merging any copy
that names a peer, benchmarks a peer, or makes a uniqueness claim.

Snapshot date on this skill: **2026-07-08**. Anything that names a peer
version, a number, or a "unique" claim is volatile — re-verify before
publication.
