---
name: noyalib-research-frontier
description: >-
  What's next for noyalib — the open, candidate research directions where this
  library could advance the state of the art, PLUS the discipline that turns a
  hunch into an accepted result here. Frontier thesis chosen 2026-07-07:
  YAML-spec leadership — conformance beyond the official test suite, edge-case
  authority, upstream spec/suite contributions, becoming the reference
  implementation for YAML 1.2.2 ambiguities. Load when asking "is there a
  research angle here?", "what would be worth a paper / RFC / upstream PR?",
  "how do we know an idea earned its way in?", "what's a falsifiable milestone
  for a spec-conformance push?". Ambitions are OPEN and CANDIDATE; nothing on
  this page is a v0.1.0 commitment. Covers the frontier thesis, four open
  problem statements with first-three-steps grounded in this repo, and the
  research methodology (evidence bar, hypothesis-predicts-numbers, idea
  lifecycle) that has produced the results noyalib already ships. Dated
  2026-07-07.
---

# noyalib Research Frontier

> **Progressive disclosure.** The bulk of this skill — the four full
> open-problem statements and the verbatim worked examples — lives in
> [`reference.md`](./reference.md). This page is the compact index:
> thesis, problem index, methodology rules, non-goals, cross-refs,
> provenance.

Open problems + the discipline. Nothing here is committed roadmap; everything
is a **candidate** direction with a falsifiable "you have a result when…"
milestone attached.

- Audience: mid-level engineer or Sonnet-class model with time to spend on
  research-shaped work (weeks, not hours).
- Scope: pure-Rust YAML library `noyalib` v0.0.14.
- Frontier thesis (chosen 2026-07-07): **YAML-spec leadership**. Conformance
  beyond the official test suite; edge-case authority; upstream spec/suite
  contributions; the reference implementation for YAML 1.2.2 ambiguities.
- Date-stamp: 2026-07-07. Every claim below carries a re-verify command so it
  can be re-checked before being repeated.
- Not this skill:
  - Positioning / marketing claims → `noyalib-external-positioning`.
  - Executing a measured campaign (coverage, benchmark chase) →
    `noyalib-coverage-campaign`.
  - Settled battles → `noyalib-failure-archaeology`.
  - Live triage → `noyalib-debugging-playbook`.

---

## Provenance — re-verify before quoting numbers

Everything volatile below was captured 2026-07-07. Re-run before repeating:

```sh
grep -n "skip" crates/noyalib/tests/official_suite.rs | head
grep -n "SKIP_LIST\|skip" crates/noyalib/tests/yaml_compliance_report.rs | head
ls crates/noyalib/tests/yaml-test-suite/*.yaml | wc -l
grep -c '^#\[test\]' crates/noyalib/tests/competitor_bugs.rs
ls fuzz/fuzz_targets/fuzz_diff.rs fuzz/fuzz_targets/fuzz_yaml_v1_1.rs \
    fuzz/fuzz_targets/fuzz_strict.rs
```

Captured 2026-07-07 (label: candidate, not target):

- `SKIP_LIST` in both `official_suite.rs` and `yaml_compliance_report.rs`
  is `&[]`. The regression net treats the entire suite as active — any
  future skip has to be argued for in writing in the same file.
- Bundled suite copy: ~351 `.yaml` case wrappers.
- Competitor-bug fixtures: 27 `#[test]` entries in `competitor_bugs.rs`.
- Differential fuzz targets present: `fuzz_diff`, `fuzz_yaml_v1_1`,
  `fuzz_strict`, plus `fuzz_no_span_loader`, `fuzz_double_quoted`,
  `fuzz_borrowed_alias`, `fuzz_multi_doc`, `fuzz_parse`, `fuzz_roundtrip`,
  `fuzz_from_value`.

If any has drifted, use the new number — do not quote this page.

---

## Frontier thesis

**No Rust YAML crate is treated by the ecosystem as the arbiter of YAML
1.2.2 ambiguities.** The seat is empty; noyalib has the minimum viable
base camp to compete for it. Five on-the-ground assets justify that
claim: a full-suite runner that generates a categorised gap report (not
a pass-rate badge); strict-1.2-by-default posture (ADR-0002); a
27-entry `competitor_bugs.rs` corpus already cross-referenced to peer
tickets; a CST (ADR-0001) that can represent byte-exact edge cases; and
a `fuzz_diff` harness already running noyalib × `serde_yaml_ng` ×
`saphyr`. Not "noyalib is the arbiter now" — "the seat is empty and
this codebase has the tooling to compete for it".

Full evidence table (all five assets, spec-§ citations, SOTA-failure
statement in long form): see
[reference.md § Frontier thesis — evidence (extended)](./reference.md#frontier-thesis--evidence-extended).

---

## Open-problems index

Each is a **candidate** direction with a `first-three-steps` block and a
falsifiable `Result-when` milestone. Full narrative for each in
`reference.md`.

- **(a) Close the skipped-case set** — `SKIP_LIST = &[]` is a published
  zero; each future skip needs written spec-§ rationale.
  → [reference.md § Open problem (a)](./reference.md#open-problem-a--close-the-skipped-case-set)
- **(b) Edge-case conformance database beyond the suite** — lift
  `competitor_bugs.rs` + failure-archaeology into a citable
  spec-referenced corpus other crates can adopt.
  → [reference.md § Open problem (b)](./reference.md#open-problem-b--edge-case-conformance-database-beyond-the-suite)
- **(c) Upstream spec/suite contributions** — push `fail-lenient` and
  `fail-value-mismatch` cases into yaml-test-suite / spec errata rather
  than treating the suite as read-only.
  → [reference.md § Open problem (c)](./reference.md#open-problem-c--upstream-specsuite-contributions)
- **(d) Differential conformance harness as a service** — turn
  `fuzz_diff`'s abort stream into a per-release published divergence
  table, cited externally.
  → [reference.md § Open problem (d)](./reference.md#open-problem-d--differential-conformance-harness-as-a-service)

---

## Research methodology summary

Compact rule list. Each rule has a specific failure mode in this
codebase it's protecting against; the verbatim worked examples that
justify each rule live in [reference.md § Research methodology —
worked examples](./reference.md#research-methodology--worked-examples).

**Evidence bar.**

- One mechanism must explain ALL observations, including negatives. A
  hypothesis that says "X causes symptom A" but doesn't say why
  X-adjacent symptom A' is absent is under-specified. → see
  [silent-collapse worked example](./reference.md#worked-example--silent-collapse-evidence-bar).
- Adversarial refutation before landing: assign someone (Sonnet-class
  model, or yourself in an adversarial seat) to find the counter-example.
  Counter-example landing = hypothesis wrong or scope narrower than
  claimed; both are findings.

**Hypothesis predicts numbers.**

- Benchmark expectations written down **before** the run. If the number
  lands where predicted, that's a much stronger signal than "looks fine".
  → see [merge-key clone gate worked example](./reference.md#worked-example--merge-key-clone-gate-numbers-before-running).
- If the number lands and the prediction wasn't written first, you
  don't know whether the mechanism you *think* explains it actually did.

**Idea lifecycle.**

1. Experiment (bench, fuzz target, throwaway branch — cheap, disposable).
2. Cross-path validation across the ~4-5 parse entry points (`from_str`,
   `load_all_as`, `cst::parse_document`, `Loader`, `NoSpanLoader`).
3. Change-control PR (spec § or failing test cited; CI green on every
   feature-matrix job; regression test shipped or written refusal).
4. Adopted OR documented retirement (fizzled directions → failure-
   archaeology "Attempted, not adopted").

**Where good ideas historically came from.** Community PRs (#117, #118)
that were narrow + spec-cited + tested; incident follow-ups (every
failure-archaeology entry began this way); competitor-bug mining;
bench regressions. Full form in
[reference.md § Where good ideas historically came from](./reference.md#where-good-ideas-historically-came-from).

---

## Non-goals (fenced — do not spend research budget here)

- **YAML 1.3 / 2.0 speculation.** No stable target. 1.2.2 is the active
  spec; research work targets it.
- **Forking the yaml-test-suite.** Contribute upstream. A private fork
  loses the "citable common floor" property that makes conforming to
  the suite meaningful.
- **Trading the strict-1.2 default for compatibility wins.** ADR-0002
  is settled; 1.1 semantics remain available via
  `ParserConfig::version`.
- **New feature velocity that isn't security / conformance /
  performance driven.** Per the security-first posture memory
  (2026-07-07): research budget goes to hardening, correctness, and
  the frontier thesis, not surface expansion.

---

## When NOT to use this skill

- **Marketing / positioning claims.** "noyalib is the most spec-compliant
  Rust YAML crate" is a positioning statement, not a research finding.
  → `noyalib-external-positioning` (when authored).
- **Executing a measured campaign** (coverage push, benchmark improvement,
  targeted parity work). → `noyalib-coverage-campaign` (when authored).
- **Live triage of a red CI / regression.** → `noyalib-debugging-playbook`.
- **Looking up why an existing design is shaped a particular way.** →
  `noyalib-failure-archaeology` (settled battles) or `doc/adr/` (settled
  decisions).
- **Making a change to code without a research question attached.** →
  `noyalib-change-control` for the process, `noyalib-architecture-contract`
  for the shape constraints.

---

## Re-verify this file

Before quoting anything on this page to an outside audience, re-run the
Provenance section commands. The frontier's starting inventory (skip list,
suite size, fixture count, differential-target list) is the volatile part
— everything else on this page is methodology and thesis. Methodology and
thesis don't rot on a weekly cadence, but the numbers do.

Last full re-verify: 2026-07-07.
