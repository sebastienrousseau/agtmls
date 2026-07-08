---
name: noyalib-failure-archaeology
description: >-
  The chronicle of noyalib's settled battles. Load BEFORE proposing a
  fix, refactor, or "I noticed X is shaped oddly" change. Answers "has
  this been tried?", "why is X shaped that way?", "is there a known
  regression history for this area?", "was this ever reverted?",
  "check history before I propose X", "look up the incident behind Y",
  or "explain the story of Z". Covers the cache-poisoning no_std mask,
  the distinct-typed key- collision campaign (loader parity + nan-key
  follow-on), BOM column desync, lone-CR line breaks, alias span
  misdirection, FlowStyle ignored, #46 depth-counter imbalances,
  RUSTSEC/cargo-vet trust-chain gaps, and workspace-split
  shared-workflow caller permissions. Each entry: symptom → root
  cause → evidence (commit SHA + file) → status → what NOT to retry.
  Dated 2026-07-08.
---

# noyalib Failure Archaeology

The chronicle. Every entry is a battle already fought. Read the entry
that matches your area BEFORE you touch it — several are booby-trapped
with settled middles where the naive fix is one of the already-rejected
paths.

- Audience: mid-level engineer or Sonnet-class model.
- Scope: `noyalib` v0.0.14 and its CI/supply chain.
- Not this skill: live triage → `noyalib-debugging-playbook`; rules
  extracted from these incidents → `noyalib-change-control`.
- Dated: 2026-07-08.

> **Full chronicle in `reference.md`** — this file is the index and
> the load-bearing DO NOT RETRY summary. Jump to
> `reference.md#entry-N-...` for the full symptom / root cause /
> evidence / DO NOT RETRY narrative of any entry. The SHA
> re-verification one-liner for all 25 references and the "how to
> add an entry" template also live in `reference.md`.

## How to use

1. Scan the **incident index** below by area. Each row points to
   `reference.md § Entry N`.
2. Read the matching entry end-to-end in `reference.md`. Respect
   **DO NOT RETRY**.
3. Cross-check your proposed change against the compact
   **DO NOT RETRY summary** further down.
4. If the issue recurs: append a new entry to `reference.md`
   (template there) and add a row here.

---

## Incident index

| # | Entry (→ `reference.md`) | One-line | Status |
|---|--------------------------|----------|--------|
| 1 | [Cache-poisoning no_std mask](reference.md#entry-1--cache-poisoning-no_std-mask-v009--v0011) | Swatinem cache served std-on artifacts to the no_std job; sub-2s warm checks replayed cached success. | SETTLED v0.0.11 |
| 2 | [Silent distinct-typed key collapse on Value fast path](reference.md#entry-2--silent-distinct-typed-key-collapse-on-the-value-fast-path-v0014) | `KeyCollision` guard on span-full loader only; `NoSpanLoader` + serde streaming silently dropped entries. Four sibling parity gaps. | SETTLED v0.0.14 |
| 3 | [The nan-key follow-on](reference.md#entry-3--the-nan-key-follow-on-v0014-campaign) | Raw-string keys broke collision detection; `{:?}` on floats leaked Rust Debug spelling (`"NaN"`). Canonical YAML spellings are the settled middle. | SETTLED v0.0.14 |
| 4 | [BOM column desync](reference.md#entry-4--bom-column-desync-v0010-community-pr-118-by-zoosky) | Leading UTF-8 BOM's 3 bytes counted as indent in three scanner sites; multi-node docs errored. | SETTLED v0.0.10 |
| 5 | [Lone-CR line breaks](reference.md#entry-5--lone-cr-line-breaks-v0014-issue-147) | Classic-Mac CR-only endings rejected — scanner matched LF/CRLF only in three sites. | SETTLED v0.0.14 |
| 6 | [Alias span misdirection](reference.md#entry-6--alias-span-misdirection-v0014-issue-149) | `span_at` on `b: *anc` returned the dangling `*anc` lexeme instead of the anchor value span. | SETTLED v0.0.14 |
| 7 | [FlowStyle config ignored](reference.md#entry-7--flowstyle-config-ignored-v008-issue-84) | `SerializerConfig::flow_style` wired to setter, not reader; emit path never consulted it. | SETTLED v0.0.8 |
| 8 | [#46 depth-counter imbalances](reference.md#entry-8--issue-46-depth-counter-imbalances-v006) | Two peers: streaming depth leak on empty flow maps + `NoSpanLoader` incremented depth but never compared to limit. | SETTLED v0.0.6 |
| 9 | [RUSTSEC / cargo-vet trust-chain gaps](reference.md#entry-9--rustsec-responses--cargo-vet-trust-chain-gaps) | Publisher change breaks trust chain even on legitimate bumps; `cargo vet fmt` strips TOML comments. | SETTLED (doctrine) |
| 10 | [Shared-workflow caller permissions](reference.md#entry-10--workspace-split-shared-workflow-caller-permissions-adr-0005-v0012-13) | Satellite pilot startup-failed with 0 jobs, no annotation — callee `permissions` scope not unioned by caller. | SETTLED (doctrine) |

---

## DO NOT RETRY — compact summary

The load-bearing use of this skill. Before proposing a change,
check whether it appears here. Full context: click through to the
matching entry in `reference.md`.

### Cache / CI integrity (Entry 1)
- Do not consolidate `CARGO_TARGET_DIR` across feature-matrix jobs
  to "reduce disk usage".
- Do not delete the wasm32 bare-metal job as "redundant with
  `--no-default-features`".
- Do not trust sub-2s `cargo check` on feature-matrix jobs as
  proof of compilation.

### Value fast path / key collision (Entries 2 & 3)
- Do not route `Value` through streaming when `TagRegistry` is
  off "to simplify" — bypass exists because streaming visitor
  loses the typed key.
- Do not clone mapping keys unconditionally — the
  `is_buffered_merge_key` gate prevents merge-heavy regression.
- Do not add a new deserialization entry point without a parity
  test.
- **Raw-key mode is INCOMPATIBLE with typed collision detection.**
  Do not re-propose "just keep keys as source spellings".
- Do not switch `value_to_key_string` to `format!("{:?}", ...)`
  or `format!("{}", ...)` for floats without nan/inf/-inf
  special-casing.
- Do not add a "raw-key opt-in" knob without gating collision
  detection off in that mode.

### Scanner / byte-faithfulness (Entries 4 & 5)
- Do not skip the BOM at the reader layer — must reach trivia.
- Do not fix only the BOM column counter — simple-key indent and
  comment-preceded-by-whitespace are independent callers.
- Do not normalize line endings at the reader layer — scanner
  must preserve byte offsets for CST round-trip.
- New line-break-sensitive sites must match all three forms:
  LF, CR, CRLF.

### CST walker (Entry 6)
- Do not add `AliasMark` back to `is_value_property_kind` —
  anchor definitions and alias references are structurally
  asymmetric.
- Do not "make aliases self-contained" by inlining anchor bytes
  at scan time — CST round-trip requires aliases stay lexically
  preserved.

### Serializer config (Entry 7)
- Every new `SerializerConfig` field needs a builder test AND an
  emit-path assertion. No builder-coverage-only merges.

### Depth / DoS guards (Entry 8)
- Do not add a new `MapAccess` / `SeqAccess` impl without a
  `finished` flag consulted from **both** `next_key_seed` and
  `next_value_seed`.
- Do not add a new load path without a `max_depth` check on
  every `MappingStart` / `SequenceStart`.
- Do not raise default `max_depth` above 128 as a workaround —
  the counter is wrong, not the limit.

### Supply chain (Entry 9)
- Do not put exemption rationale in a TOML comment — `cargo vet
  fmt` deletes it. Put it in the commit message body.
- Do not "extend trust" without an actual audit.
- Do not batch a RUSTSEC bump into a large release without
  budgeting for a CI storm.

### Shared workflows / satellites (Entry 10)
- Do not diagnose a 0-jobs-no-annotation startup-fail as a
  "flaky runner" — almost always a permissions mismatch.
- Do not narrow a shared workflow's `permissions` block after
  release without auditing every satellite caller.
- Do not use `permissions: write-all` in a satellite to sidestep
  the union.

---

## See also (sibling skills)

- **`noyalib-debugging-playbook`** — live triage (red CI check,
  active crash bisect). Reproduction, bisect, hypothesis loops.
  This skill is retrospective; that one is real-time.
- **`noyalib-change-control`** — rules-of-engagement extracted
  from these incidents (e.g. "every new load path needs a
  max_depth check"). Codified policy layer; this is the raw
  evidence layer.

## When NOT to use this skill

- **Live triage** (red CI check, active crash bisect): use
  `noyalib-debugging-playbook`. This skill is for retrospective
  "has this been settled before?" lookups.
- **Rules-of-engagement** extracted from these incidents: use
  `noyalib-change-control`.

## Provenance

All 25 commits referenced in `reference.md` were live in `main`
on 2026-07-07. The SHA re-verification one-liner and search
recipes are in `reference.md § SHA re-verification one-liner`.

Long-form commit bodies are ground truth; release notes are a
readable secondary; issue numbers (`#118`, `#149`, `#152`, `#46`,
`#84`, `#147`) are stable GitHub pointers. Subject lines are
often misleading — read the body:

```sh
git show <sha> -s --format="%h %s%n%n%b"
```
