# noyalib Research Frontier — Reference

Complements [`SKILL.md`](./SKILL.md) (skill: `noyalib-research-frontier`).
Date-stamp: 2026-07-07.

This file holds the bulk material that was split out of SKILL.md under
progressive-disclosure rules: the four full open-problem statements and
the worked examples from the research-methodology section. SKILL.md
keeps the frontier thesis, an index of open problems, a compact
methodology rule list, non-goals, cross-refs, and provenance.

---

## Frontier thesis — evidence (extended)

The [thesis in SKILL.md](./SKILL.md#frontier-thesis) claims spec
leadership is winnable HERE because of five on-the-ground assets. The
full form of that claim:

1. **Full-suite integration with a gap-report generator, not a pass/fail
   badge.** `tests/official_suite.rs` runs the whole suite as the
   regression net; `tests/yaml_compliance_report.rs` classifies failures
   (`fail-parse-error`, `fail-value-mismatch`, `fail-lenient`,
   `fail-non-scalar-key`) and writes `target/yaml-compliance-report.md`.
   Peers surface a single pass-rate number; noyalib surfaces a
   **categorised gap inventory** — the primary input to a conformance
   research program.
2. **Strict-1.2-by-default posture** (`doc/adr/0002-yaml-1.2-default.md`).
   Peer crates default to looser 1.1-flavoured resolution to protect
   existing users. noyalib does not carry that constraint. Every
   over-lenient acceptance in the ecosystem is a candidate research
   finding here.
3. **Competitor-bugs fixture suite** (`tests/competitor_bugs.rs`, 27
   tests). Each entry reproduces a known issue from another Rust YAML
   crate — the embryo of a citable YAML-1.2.2 edge-case database.
4. **A CST that can represent byte-exact edge cases** (ADR-0001,
   `doc/adr/0001-cst-rowan-shape.md`). Round-trip preservation means a
   corner-case fixture can be represented, formatted, and compared
   without value-level projection erasing what makes it interesting.
5. **Differential harness already wired to two peers.** `fuzz_diff`
   compares noyalib, `serde_yaml_ng`, `saphyr` on inputs all three
   accept, and panics on divergence. Runnable core of a "which crate
   does what on which corner" report.

The SOTA failure the thesis targets: **no Rust YAML crate is treated by
the ecosystem as the arbiter of YAML 1.2.2 ambiguities.** The official
test suite itself has known gaps and cases where implementations
disagree for defensible reasons (directive-marker enforcement §6.8,
CR-only line breaks §5.4). That arbiter seat is open. Claim: noyalib's
infrastructure is the minimum viable base camp for a serious attempt at
it. Not "noyalib is the arbiter now" — "the seat is empty and this
codebase has the tooling to compete for it".

---

## Open problem (a) — Close the skipped-case set

The frontier's starting inventory is the deliberately-skipped set. Any
future `SKIP_LIST` entry's reason string becomes the next research question.

**Why SOTA fails.** Rust YAML crates that publish suite pass rates carry
an implicit skip list — cases they quietly can't handle — that never
surfaces to users. `official_suite.rs`'s SKIP_LIST convention is the
opposite: `&[]` today, and any addition requires a `(file_id, reason)`
tuple that survives review.

**noyalib's specific asset.**

- `SKIP_LIST = &[]` in both runners on 2026-07-07 — a **published zero**.
- `yaml_compliance_report.rs::classify` distinguishes four failure modes
  (`fail-parse-error`, `fail-value-mismatch`, `fail-lenient`,
  `fail-non-scalar-key`) — each maps to a different research response.
- Regression net floors at 94% compliance; report runner floors at ≥350
  loaded cases so a wrapper-parse regression can't vacuously 100%-pass.

**First three concrete steps IN THIS REPO.**

1. Run `cargo test -p noyalib --test yaml_compliance_report -- --nocapture`;
   copy `target/yaml-compliance-report.md` into a working note. The
   `Failures` section IS the categorised gap inventory.
2. For each `fail-lenient` case, cite the exact YAML 1.2.2 §rule the
   lenient acceptance violates. Draft either (a) a strictness fix in
   `scanner`/`parser` with a fuzz corpus seed, or (b) a written principled
   refusal (must survive adversarial review — "what breaks in the wild if
   you tighten this?").
3. For each `fail-non-scalar-key` case, decide as a class: represent
   typed-key mappings, OR keep the String-keyed `Value::Mapping` model
   and make these principled refusals citing ADR-0002 + failure-
   archaeology Entry 2.

**Result-when.** Any future `SKIP_LIST` entry carries a written spec-§
rationale that survives adversarial refutation. Skip count either stays
zero OR each added skip is publishable justification, not an omission.

---

## Open problem (b) — Edge-case conformance database beyond the suite

The official suite is the shared floor. The ceiling is the union of all
edge cases anyone has ever fixed. That union is not curated anywhere —
each Rust YAML crate has its own regression-tests directory, and they
don't cite each other.

**Why SOTA fails.** No Rust YAML crate publishes a citable, spec-referenced,
externally-consumable edge-case corpus. Bugs fixed in one crate don't
propagate to peers because the fix ships as a private `#[test]` file, not a
data set with expected behaviours.

**noyalib's specific asset.**

- `tests/competitor_bugs.rs` — 27 tests as of 2026-07-07, each already
  cross-referenced to the upstream ticket (yaml-rust2 #23, #25, #30, #69,
  #70, etc.). This is a corpus in embryonic form.
- `tests/spec/` — 15+ file organisation split by spec area
  (`anchors_aliases.rs`, `block_scalars.rs`, `comments.rs`, `edge_cases.rs`,
  `flow_collections.rs`, `mappings.rs`, `multi_document.rs`, `nested.rs`,
  `null_bool.rs`, `numbers.rs`, `scalars.rs`, `sequences.rs`,
  `special_keys.rs`, `tags.rs`). Each file already partitions by spec
  concern.
- Incident corpus from historical fixes: lone-CR line breaks, BOM column
  desync, chomping edge cases, distinct-typed key collisions — every entry
  in `noyalib-failure-archaeology` is a candidate corpus row.

**First three concrete steps IN THIS REPO.**

1. Author a lift: extract from `tests/competitor_bugs.rs` and the failure-
   archaeology into a `docs/edge-cases/*.yaml`-shaped set of case files.
   Follow the yaml-test-suite wrapper format (fields: `name`, `yaml`,
   `json`, `fail`, `tags`) so the corpus is drop-in for the suite runner
   plus a spec-section citation field (`spec_ref: "1.2.2 §6.8"`).
2. Wire a second runner (`tests/edge_cases_corpus.rs`) that loads the
   local corpus with the same wrapper decoder as `official_suite.rs` and
   asserts noyalib's behaviour against the expected JSON / fail flag.
3. Reach out to one peer maintainer with a fixture — e.g. offer the
   lone-CR fixture to `saphyr` or `yaml-rust2` — as a self-contained YAML
   file with expected behaviour and spec citation. Adoption is the
   external validation signal.

**Result-when.** An external Rust YAML crate either adopts a fixture from
the corpus, or a fix in another crate cites a case ID from it. Either
event turns "our internal regression suite" into "a citable ecosystem
resource".

---

## Open problem (c) — Upstream spec/suite contributions

The official yaml-test-suite has known gaps. Directive-marker enforcement
(§6.8), CR-only line breaks (§5.4), duplicate-key handling (§3.2.1.3),
and non-scalar key semantics are all areas where implementations diverge
and the suite either doesn't cover the corner or has a case that different
implementations pass/fail differently.

**Why SOTA fails.** Most implementation authors treat the suite as read-
only ("we conform to it"). Very few push cases back the other way. The
suite therefore grows more slowly than the implementations do, and
ambiguity gets embedded rather than adjudicated.

**noyalib's specific asset.**

- Strict-1.2 posture (ADR-0002) surfaces ambiguities other crates paper
  over. Every `fail-lenient` category in the compliance report is a
  candidate for an upstream case.
- Long-form commit bodies document the spec § consulted for each fix
  (see `noyalib-failure-archaeology` for examples; the pattern is:
  symptom → §rule → decision → fix).
- Zero-unsafe policy (ADR-0003) and pure-Rust posture reduce the "is this
  a noyalib quirk or a spec matter?" ambiguity — behaviour comes from the
  source, not from an FFI'd libyaml.

**First three concrete steps IN THIS REPO.**

1. From the current `yaml-compliance-report.md`, pick one `fail-lenient`
   case where noyalib rejects, other implementations accept, and the spec
   §rule is unambiguous. Draft the case in yaml-test-suite wrapper
   format, with two expected behaviours (accept + expected JSON, OR
   fail-with-reason) and a §citation.
2. Open a yaml-test-suite issue proposing the case; if the response is
   "we already have this", link the existing case ID and stop. If not,
   PR the case with the spec §citation and the noyalib output as the
   reference behaviour.
3. Repeat for a `fail-value-mismatch` case where noyalib and the
   suite's expected-JSON disagree AND the spec §rule is on noyalib's
   side. This is the harder class because it's "the suite has a bug",
   not "the suite is missing a case".

**Result-when.** A case authored here is merged upstream into
yaml-test-suite, OR an upstream issue drives a spec-committee
clarification cited in a spec erratum. Either lands noyalib in the
conformance conversation with more than opinion.

---

## Open problem (d) — Differential conformance harness as a service

`fuzz_diff` already runs noyalib × `serde_yaml_ng` × `saphyr` and panics
on divergence. That output is a stream of aborts, not a report.

**Why SOTA fails.** No published resource says "on YAML corner X, crate
A produces Y, crate B produces Z, crate C rejects." Users pick a Rust
YAML crate by trailing GitHub stars and the last release date. The
correctness-alignment axis is invisible.

**noyalib's specific asset.**

- `fuzz/fuzz_targets/fuzz_diff.rs` — three-way parser diff already
  running, with `numeric_equal` normalising the int/float representation
  gap.
- Multiple sibling differential targets: `fuzz_yaml_v1_1` for 1.1-mode
  behaviour, `fuzz_strict` for strict-mode acceptance, `fuzz_no_span_loader`
  for the span-full vs streaming loader parity (see failure-archaeology
  Entry 2 for how that target caught the silent-collapse bug).
- The categorised failure modes from problem (a) are the natural rows
  for a per-case matrix.

**First three concrete steps IN THIS REPO.**

1. Fork `fuzz_diff` into a `bench`-style binary that reads corpus files
   (rather than libFuzzer inputs) and writes a `divergences.md` grouped by
   corner. Rows: case ID + snippet. Columns: noyalib, serde_yaml_ng,
   saphyr, expected (if from a suite case). Cells: parsed JSON or the
   error class.
2. Point the binary at the union of `tests/yaml-test-suite/` and the
   edge-case corpus from problem (b). Commit the generated report under
   `target/` (git-ignored) and print the diff-summary to stderr — the
   report is a build product, not a source artefact.
3. Add the divergence-report generation to the release checklist so each
   release ships a snapshot of the state-of-the-ecosystem-on-YAML-corners
   at that tag. It becomes a versioned external reference.

**Result-when.** A reproducible divergence table is published per release
and cited externally (peer README, blog, spec-committee discussion). The
value here is public-goods infrastructure, not a noyalib win — the point
is that noyalib maintains the infrastructure.

---

## Research methodology — worked examples

The compact rule list lives in [SKILL.md → Research methodology
summary](./SKILL.md#research-methodology-summary). The verbatim worked
examples that justify each rule live here.

### Worked example — silent-collapse (evidence bar)

**Rule.** One mechanism must explain ALL observations, including negatives.
A hypothesis that says "X causes symptom A" but doesn't say why X-adjacent
symptom A' is absent is under-specified.

**Case (v0.0.14, failure-archaeology Entry 2).**
`from_str::<Value>` on `"1: a\n\"1\": b"` returned a single-entry map;
`cst::parse_document` on the same bytes raised `Error::KeyCollision`.
Naive hypothesis "the collision guard is buggy" was rejected — it didn't
explain the CST-path success. Refined hypothesis "the streaming visitor
path can't SEE the typed key, so the guard is unreachable on that path"
predicted BOTH the Value-path failure AND the cst-path success before the
fix was drafted. The hypothesis' broader prediction — that any other
config knob whose enforcement lives on the streaming path is similarly
bypassable — drove the audit that found four adjacent holes
(`max_sequence_length`, `max_mapping_keys`, `max_merge_keys`, the
billion-laughs `alias_bytes` cap), all fixed in the same commit. Had the
hypothesis only explained the reported symptom, three of five holes ship.

**Adversarial refutation.** Before landing a research-shaped change,
assign someone (a Sonnet-class model, or yourself in an adversarial seat)
to find the counter-example. Counter-example landing = hypothesis wrong,
or scope narrower than claimed. Both are findings.

### Worked example — merge-key clone gate (numbers before running)

**Rule.** Benchmark expectations written down **before** the run. If the
number lands where predicted, that's a much stronger signal than "looks
fine".

**Case.** Before landing the `is_buffered_merge_key` gate in the
distinct-typed key fix, the prediction was `merge_heavy` bench parity
with `integer_keys` (merge documents no longer paying the mapping-key
clone cost). Bench matched. Had it come back 1.4× slower, the hypothesis
— not the bench — would have been the thing to re-examine.

Rule tightening: if the number lands and the prediction wasn't written
first, you don't know whether the mechanism you *think* explains it
actually did.

### Idea lifecycle (long form)

1. **Experiment.** Bench, fuzz target, draft test, throwaway branch —
   cheap and disposable. Artefact locations: `crates/noyalib/benches/`,
   `fuzz/fuzz_targets/`, `tests/spec/edge_cases.rs`.
2. **Cross-path validation.** ~4-5 parse entry points (`from_str`,
   `load_all_as`, `cst::parse_document`, `Loader`, `NoSpanLoader`) must
   see the same behaviour. Cross-path fuzzing (`fuzz_no_span_loader`,
   `fuzz_diff`) surfaces the paths a naive fix missed.
3. **Change-control PR.** Per `noyalib-change-control`: commit body
   cites spec § or failing test; CI green on every feature-matrix job;
   PR ships a regression test or explains in writing why it can't.
4. **Adopted OR documented retirement.** Fizzled directions go in
   `noyalib-failure-archaeology` under "Attempted, not adopted" so
   future engineers know it was tried.

### Where good ideas historically came from

- **Community PRs #117 / #118.** `lossless-u64` opt-in (@canardleteer),
  seq-key spec case (@zoosky). Landed because they were narrow, spec-
  cited, and shipped with tests. Replicate this shape when evaluating
  future external work.
- **Incident follow-ups.** Every failure-archaeology entry began as an
  incident follow-on. The distinct-typed key campaign grew from a
  single-collision bug into a five-hole audit. Always ask "what
  adjacent surface uses the same mechanism, and is it actually protected?"
- **Competitor-bug mining.** `tests/competitor_bugs.rs` was seeded from
  yaml-rust2's issue tracker. Cheapest source of edge cases — someone
  else already did the reduction.
- **Bench regressions.** The merge-key clone gate would not have been
  found without the `merge_heavy` bench. Every performance claim needs
  a bench that catches its violation.

---

## Cross-refs back to SKILL.md

- [Frontier thesis (summary)](./SKILL.md#frontier-thesis)
- [Open-problems index](./SKILL.md#open-problems-index)
- [Research methodology summary](./SKILL.md#research-methodology-summary)
- [Non-goals](./SKILL.md#non-goals)
- [Provenance](./SKILL.md#provenance--re-verify-before-quoting-numbers)
