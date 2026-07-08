# noyalib-external-positioning — reference material

Complements `SKILL.md` in this directory. Snapshot date **2026-07-08**;
the ecosystem drifts — re-verify every peer row and number before
shipping copy. `SKILL.md` keeps the ground-truth file list, the
provable differentiators (each with where the proof lives), and the
claiming rules (project law). This file keeps the ecosystem map, the
reproducibility standards, the migration-audience playbook, and the
pre-publication provenance checklist.

---

## R1. Ecosystem map (2026-07 — verify each row before publication)

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

## R2. Reproducibility standards

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

## R3. Migration-audience playbook

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

## R4. Provenance / re-verification checklist

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

Snapshot date on this skill: **2026-07-08**. Anything that names a peer
version, a number, or a "unique" claim is by definition volatile.
Re-verify before publication.
