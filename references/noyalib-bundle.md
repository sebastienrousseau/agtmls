<!-- SPDX-FileCopyrightText: 2026 Noyalib -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->

# noyalib skill library — routing index

14 skills covering change management, debugging, architecture, YAML domain,
config, build/env, CI/release, diagnostics, QA, docs, positioning,
coverage, and research for
[noyalib](https://github.com/sebastienrousseau/noyalib) (pure-Rust YAML 1.2,
zero `unsafe`, currently v0.0.14 on branch `feat/v0.0.14`).

Skills are gitignored (`.claude/` is local-only); each is a self-contained
runbook that a Sonnet-class session or a mid-level engineer can load cold.

Dated 2026-07-08.

## The 14 skills

| Skill | One-line purpose |
|---|---|
| `noyalib-change-control` | Rulebook: classify a change, pick its gates, judge release readiness. |
| `noyalib-debugging-playbook` | Symptom-driven triage — which of the three loaders is my bug in. |
| `noyalib-failure-archaeology` | Chronicle of settled battles; check history before proposing a fix. |
| `noyalib-architecture-contract` | Load-bearing design decisions + invariants that must hold. |
| `yaml-domain-reference` | YAML 1.2.2 spec knowledge as noyalib implements it. |
| `noyalib-config-and-flags` | Catalog of every Cargo feature + `ParserConfig` / `SerializerConfig` axis. |
| `noyalib-build-and-env` | Recreate a working dev env from scratch; toolchain / MSRV / Apple-Silicon traps. |
| `noyalib-ci-and-release` | Runbook: operating CI, cache-poisoning doctrine, tag-driven release. |
| `noyalib-diagnostics-and-tooling` | Measure instead of eyeball — coverage, Miri, criterion, cargo-fuzz. |
| `noyalib-validation-and-qa` | What counts as evidence; test taxonomy; acceptance thresholds. |
| `noyalib-docs-and-writing` | Docs of record + house rustdoc / commit-message / SPDX style. |
| `noyalib-external-positioning` | Ecosystem map + claiming rules for anything the project says in public. |
| `noyalib-coverage-campaign` | Decision-gated playbook to drive coverage to the 98 % target. |
| `noyalib-research-frontier` | Open candidate directions + methodology to earn a result. |

## Router — which skill for which question

| Question | Load |
|---|---|
| "Am I allowed to do X?" / "what gates does this need?" | `noyalib-change-control` |
| "Why does `from_str::<Value>` disagree with `cst::parse_document`?" | `noyalib-debugging-playbook` |
| "Has this bug been investigated before?" / "was this ever reverted?" | `noyalib-failure-archaeology` |
| "Can I change the three-loader routing?" / "what invariants apply here?" | `noyalib-architecture-contract` |
| "Explain YAML merge keys / anchors / chomping / the Norway problem." | `yaml-domain-reference` |
| "What's the default for `max_depth`?" / "how do I add a `ParserConfig` axis?" | `noyalib-config-and-flags` |
| "Fresh clone, `cargo build` fails." / "Miri won't run." / "cargo-fuzz on M-series." | `noyalib-build-and-env` |
| "CI is red." / "how do I ship v0.0.15?" / "cargo-vet failure." | `noyalib-ci-and-release` |
| "Prove this optimisation actually helps." / "run coverage." / "read criterion output." | `noyalib-diagnostics-and-tooling` |
| "How do I add a test?" / "what evidence does this PR need?" | `noyalib-validation-and-qa` |
| "Draft `RELEASE-NOTES-v0.0.15.md`." / "SPDX header shape." / "when is an ADR required?" | `noyalib-docs-and-writing` |
| "How do I position noyalib vs `serde_yaml_ng` in the README?" | `noyalib-external-positioning` |
| "Coverage is at 93 % on `parser/loader.rs` — next step?" | `noyalib-coverage-campaign` |
| "Is there a paper / RFC / upstream PR angle here?" | `noyalib-research-frontier` |

## Split routes (load both)

Some questions legitimately span two skills — load both:

| Question | Primary | Secondary |
|---|---|---|
| "Can I bump the MSRV?" | `noyalib-change-control` (breaking event, ADR) | `noyalib-build-and-env` (mechanics of `rust-version`) |
| "no_std broke but CI was green." | `noyalib-debugging-playbook` (symptom triage) | `noyalib-ci-and-release` (cache-poisoning doctrine — the CI fix) |
| "How do I write a good span-related regression test?" | `noyalib-validation-and-qa` (evidence discipline) | `noyalib-debugging-playbook` (span symptom shape) |

## Cross-reference graph (who points where)

Pairs designed to be loaded together:

```
change-control       ↔  ci-and-release          (rulebook ↔ runbook)
change-control       ↔  validation-and-qa       (gates ↔ evidence)
debugging-playbook   ↔  failure-archaeology     (live triage ↔ history)
debugging-playbook   ↔  diagnostics-and-tooling (guess ↔ measure)
architecture-contract ↔ failure-archaeology     (rules ↔ incidents)
config-and-flags     ↔  architecture-contract   (axes ↔ invariants)
config-and-flags     ↔  yaml-domain-reference   (toggles ↔ semantics)
validation-and-qa    ↔  diagnostics-and-tooling (what proves ↔ how to measure)
validation-and-qa    ↔  coverage-campaign       (evidence ↔ campaign)
docs-and-writing     ↔  ci-and-release          (docs ↔ release mechanics)
docs-and-writing     ↔  external-positioning    (internal ↔ public voice)
external-positioning ↔  research-frontier       (published claims ↔ open questions)
coverage-campaign    ↔  diagnostics-and-tooling (campaign ↔ instrument)
research-frontier    ↔  failure-archaeology     (open ↔ settled)
```

`failure-archaeology` is a design sink — every skill can point back to it,
it points only at siblings for follow-up work, and nothing depends on it
forwards. That is intentional: history is context, not gate.

## Load-bearing rules (which skills carry each)

| Rule | Skills carrying it |
|---|---|
| `forbid(unsafe_code)` workspace-wide | `change-control`, `architecture-contract`, `external-positioning` |
| Cache-poisoning doctrine (isolated `CARGO_TARGET_DIR`) | `change-control`, `ci-and-release`, `architecture-contract`, `debugging-playbook`, `build-and-env`, `diagnostics-and-tooling`, `failure-archaeology` |
| Loader-parity contract (three-loader convergence) | `architecture-contract`, `config-and-flags`, `validation-and-qa`, `failure-archaeology`, `debugging-playbook` |
| CI always green (no `--no-verify` / `[skip ci]`) | `change-control`, `ci-and-release`, `validation-and-qa` |
| No perf claim without a same-PR criterion run | `change-control`, `docs-and-writing`, `external-positioning`, `diagnostics-and-tooling` |
| Signed Conventional Commits + `Assisted-by:` trailer | `change-control`, `docs-and-writing` |
| Version-refs release audit | `change-control`, `ci-and-release`, `docs-and-writing` |
| Security > velocity | `change-control`, `ci-and-release` |
| Hand-run commands delivered as script files | `change-control`, `build-and-env` |

## Ground-truth reminders

Each skill has a **Provenance** section with runnable re-verification
commands. Before quoting a number, re-verify it. Load-bearing invariants
that drift fast:

- **MSRV**: `crates/noyalib/Cargo.toml` `rust-version` is authoritative
  (currently `1.85.0`). `doc/POLICIES.md` and `CONTRIBUTING.md` still say
  `1.75.0` — stale drift, not a distinction.
- **Coverage gate**: `.github/workflows/ci.yml` +
  `shared-coverage.yml` defaults gate at **96 fn / 94 lines / 93 regions**.
  `doc/TESTING.md` still says 95/93/92 — stale drift.
- **YAML official suite**: `tests/official_suite.rs` `SKIP_LIST = &[]`;
  94 % assertion floor; 351 wrapper files.
  `README.md` (387/387) and `doc/BENCHMARKS.md` (406/406) both drift;
  quote the test files.
- **`BudgetBreach`**: 6 variants in `error.rs`. `max_alias_expansions`
  raises `Error::RepetitionLimitExceeded`, NOT
  `BudgetBreach::MaxAliasExpansions`. `max_mapping_keys` /
  `max_sequence_length` raise `Error::Serialize(...)`. `max_depth` raises
  `Error::RecursionLimitExceeded`.
- **`unsafe` enforcement**: `#![forbid(unsafe_code)]` + `rustc`. This repo
  does NOT run `cargo geiger`.
