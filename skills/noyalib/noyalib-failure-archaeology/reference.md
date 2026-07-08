# noyalib Failure Archaeology — Reference (chronicle)

Complements `SKILL.md` (`noyalib-failure-archaeology`). Date-stamped
2026-07-08.

This file carries the full narrative for each of the ten settled
incidents indexed in `SKILL.md`. Every SHA below was verified with
`git log --oneline --all | grep <sha>` on 2026-07-07. If a SHA
drifts after a rebase, relocate via the matching
`RELEASE-NOTES-v0.0.N.md`.

Long-form commit bodies carry most of the WHY. Re-verify with:

```sh
git show <sha> -s --format="%h %s%n%n%b"
```

One-line subjects are misleading. Read the body.

---

## Entry 1 — Cache-poisoning no_std mask (v0.0.9 → v0.0.11)

**The costliest incident.** Maintainer-confirmed 2026-07-07.

### Symptom
`cargo check --no-default-features` passed green on CI for ~2 weeks
after a v0.0.9 refactor while the same command failed on any clean
local machine. no_std was actually broken; CI was returning a stale
answer.

### Root cause
`Swatinem/rust-cache` served **std-on** build artifacts to the
**no_std** job because feature-flag flips did not invalidate the
shared cache key. Sub-2s warm `cargo check` durations replayed a
cached success instead of re-invoking the compiler.

### Evidence
- `5104048` — release: v0.0.11 (CI integrity + no_std fix + cache-
  poisoning guard + ...) (#124).
- `0b2d616` — feat(no_std): core::error::Error + wasm32 CI bare-
  metal proof. Physical wasm32 build that can't use std artifacts.
- Isolation applied to 12 specialized jobs across 4 workflows.

### Fix pattern
Every specialized/feature-matrix job sets its own `CARGO_TARGET_DIR`
so Swatinem's cache key and Cargo's fingerprint agree on separation.
Extended to shared workflows in `f984e3b` for satellites.

### Status: SETTLED. Doctrine codified.

### DO NOT RETRY
- Do not consolidate `CARGO_TARGET_DIR` across feature-matrix jobs
  to "reduce disk usage" — reintroduces the mask.
- Do not delete the wasm32 bare-metal job as "redundant with
  `--no-default-features`". Plain no_std can be poisoned again;
  wasm32 physically cannot.
- Do not trust sub-2s `cargo check` on feature-matrix jobs as
  proof of compilation. That timing IS the mask.

---

## Entry 2 — Silent distinct-typed key collapse on the Value fast path (v0.0.14)

The scariest bug class in this codebase: **wrong-but-green**.
4000+ tests passing, `from_str::<Value>` silently losing data.

### Symptom
```rust
let v: Value = noyalib::from_str("1: a\n\"1\": b").unwrap();
assert_eq!(v.as_mapping().unwrap().len(), 2); // FAILS: len == 1
```
`cst::parse_document` on the same input correctly raised
`Error::KeyCollision`. `from_str::<Value>` silently dropped an
entry when two distinct YAML keys shared a string spelling (int
`1` vs str `"1"`; bool `true` vs str `"true"`; null `~` vs
str `"null"`).

### Root cause
`KeyCollision` guard was added to the span-full `Loader` in v0.0.13
(`0fff9dd` / `9bef479`) but the sibling `NoSpanLoader` and the
serde streaming `ValueVisitor::visit_map` path — **both used by
`from_str::<Value>`** — were untouched. Keys stringify into
`Mapping<String, Value>`, so distinct typed keys collided
silently at the map level.

Audit surfaced four more parity gaps on the same fast path:
`max_sequence_length`, `max_mapping_keys`, `max_merge_keys`, and
the billion-laughs `alias_bytes > max_document_length` cap all
unenforced. `MergeKeyPolicy::Error` and `DuplicateKeyPolicy`
silently ignored. `max_document_length` bypassable when streaming
was skipped.

### Evidence
- v0.0.13 span-full guard: `0fff9dd` / `9bef479`,
  `crates/noyalib/src/parser/loader.rs`.
- v0.0.14 parity fix: `bc8f798` — "fix(loader): plug distinct-
  typed key collision on Value fast path".
- Cross-path fuzz: `1e507e4` — "feat(bench,fuzz): mapping-key
  clone bench + no-span-loader fuzz".
- Regression tests: `crates/noyalib/tests/no_span_loader_parity.rs`
  (nine cases, every one fails without the fix).

### Fix pattern
Streaming is **bypassed** for `Value` target unless a `TagRegistry`
is active — otherwise `ValueVisitor::visit_map` never sees the
typed key and the collision guard is unreachable. Typed-key
`Value::clone()` for the collision check is gated by
`is_buffered_merge_key` so `<<`-heavy documents don't pay the
clone cost.

### Status: SETTLED v0.0.14. `fuzz_no_span_loader` diffs the paths.

### DO NOT RETRY
- Do not route `Value` through streaming when `TagRegistry` is
  off "to simplify". The bypass exists because the streaming
  visitor loses the typed key.
- Do not clone mapping keys unconditionally. The
  `is_buffered_merge_key` gate prevents merge-heavy regression.
- Do not add a new deserialization entry point without a parity
  test — every fast path is a potential re-run of this bug.

---

## Entry 3 — The nan-key follow-on (v0.0.14 campaign)

Sub-battle inside Entry 2. Two adjacent "obvious" designs tried,
both wrong.

### Symptom
Cycle 1 (raw-string keys): collision detection broke — int `1`
and string `"1"` have different raw spellings.
Cycle 2 (resolved keys, stringified via `{:?}`): `nan: 1`
produced key `"NaN"` (Rust's Debug spelling), not YAML canonical
`nan`. Same for `inf` / `-inf`.

### Root cause
Two mutually incompatible models were being conflated. Raw-key
mode preserves source fidelity but cannot detect distinct-typed
collisions. Resolved-key mode detects collisions but leaks Rust's
internal Debug spelling of floats.

### Settled middle
Keys are **resolved** (typed) values, and `value_to_key_string`
uses **canonical YAML spellings**: `"nan"`, `"inf"`, `"-inf"` —
not Rust's `{:?}` (`"NaN"`, `"inf"`, `"-inf"`). Documented in
the `bc8f798` commit body.

### Evidence
- `bc8f798` (see quoted commit body on canonical form).
- Search: `git log -p --all -S value_to_key_string`.

### Status: SETTLED v0.0.14.

### DO NOT RETRY
- **Raw-key mode is INCOMPATIBLE with typed collision detection.**
  Do not re-propose "just keep keys as source spellings" — you
  will either lose collision detection or reintroduce Entry 2's
  silent-drop bug.
- Do not switch `value_to_key_string` to `format!("{:?}", ...)`
  or `format!("{}", ...)` for floats without nan/inf/-inf
  special-casing. `{}` panics; `{:?}` emits `"NaN"`.
- Do not add a "raw-key opt-in" knob without gating collision
  detection off in that mode. Silent-drop must be a documented
  consequence of the opt-in.

---

## Entry 4 — BOM column desync (v0.0.10, community PR #118 by @zoosky)

### Symptom
Any multi-node document with a leading UTF-8 BOM (`U+FEFF`) failed:
```
<BOM>a: 1
b: 2
```
errored "stray content after document — subsequent documents must
start with '---'". BOM-prefixed sequences, nested mappings, and
`<BOM>#`-first-line comments failed the same way. Single-node
BOM-prefixed documents parsed **by accident** — no sibling to
trip the dedent check.

### Root cause
A leading BOM is a zero-width stream prefix, but three scanner
sites counted its 3 bytes toward the following content's column:
1. `fetch_stream_start` advanced past BOM but grew the column
   counter by 3.
2. Simple-key indent recomputed column as `sk.index - line_start`;
   on line 1, `line_start` was 0, so BOM bytes counted as indent.
3. Block-context comment check rejected `#` whose preceding byte
   wasn't whitespace/break — after a BOM that byte is `0xBF`.

### Evidence
- `71de2d9` — "fix(scanner): make a leading BOM transparent to
  indentation and comments", `crates/noyalib/src/parser/scanner.rs`.
- Release `3304f4c` — v0.0.10; `RELEASE-NOTES-v0.0.10.md`.
- Original external PR #118 (@zoosky), rebased as PR #123 with
  authorship preserved.

### Status: SETTLED v0.0.10. BOM survives as `Bom` trivia leaf so
CST round-trip stays byte-faithful.

### DO NOT RETRY
- Do not skip the BOM at the reader layer. It must reach trivia
  to preserve byte-for-byte round-trip.
- Do not fix only the column counter — the simple-key indent path
  and the comment-preceded-by-whitespace check are independent
  callers of the same wrong assumption.

---

## Entry 5 — Lone-CR line breaks (v0.0.14, issue #147)

### Symptom
Classic-Mac CR-only endings (`\r` no `\n`) were rejected.
`a: 1\rb: 2\r` errored "stray content after document" — same
symptom as Entry 4, unrelated root cause.

### Root cause
YAML 1.2.2 §5.4 defines a line break as LF, CR, or CRLF. The
scanner recognized LF and CRLF but not lone CR. Three sites
matched `\n` only: `advance()`, `advance_by()`, and the
block-mapping simple-key line-start scan.

### Evidence
- `70c77cb` / `3ad36f0` — "fix(scanner): treat lone CR as a line
  break", `crates/noyalib/src/parser/scanner.rs`.
- Regression tests in `coverage_scanner`.

### Status: SETTLED v0.0.14. Byte offsets (`pos`/`mark`) and token
spans untouched, so `source()` and round-trip are unaffected.

### DO NOT RETRY
- Do not normalize line endings at the reader layer. The scanner
  must preserve byte offsets for CST round-trip.
- If you add a new line-break-sensitive site, match all three
  forms: LF, CR, CRLF.

---

## Entry 6 — Alias span misdirection (v0.0.14, issue #149)

### Symptom
`span_at` on `b: *anc` returned the dangling `*anc` lexeme — a
standalone alias that does not re-parse. Asymmetric with anchor
definitions (`&x 1`), whose slice is self-contained.

### Root cause
An alias is a single `AliasMark` token with no value node. The
green-tree walker lumped `AliasMark` with anchor/tag property
prefixes and returned the alias's own bytes instead of falling
through to the anchor's resolved value span.

### Evidence
- `f8fe929` / `34852b2` — "fix(cst): resolve alias references
  through to the anchor value span", `crates/noyalib/src/cst/`
  walker + `SpanTree`.
- Regression tests in `cst_tag_span` — aliases to a collection,
  to a scalar, and as a sequence item.

### Fix pattern
`entry_value` / `item_value` return `None` on `AliasMark`,
`span_at` falls through to the typed cache whose `SpanTree`
carries the alias node's cloned anchor-definition span (the
loader resolves aliases at load time). `AliasMark` was dropped
from `is_value_property_kind`.

### Status: SETTLED v0.0.14.

### DO NOT RETRY
- Do not add `AliasMark` back to `is_value_property_kind`.
  Anchor definitions and alias references are structurally
  asymmetric.
- Do not "make aliases self-contained" by inlining anchor bytes
  at scan time. CST round-trip requires aliases stay lexically
  preserved.

---

## Entry 7 — FlowStyle config ignored (v0.0.8, issue #84)

### Symptom
`SerializerConfig::flow_style` was stored on the config struct
but had no effect on serialization output. Users setting flow
style saw block style.

### Root cause
`ser.rs` accepted the builder field but never consulted it in
the emit path — classic "wired to the setter, not the reader".

### Evidence
- `c528e0f` — release: v0.0.8 (FlowStyle fix + batched deps)
  (#97). Closes #84. `crates/noyalib/src/ser.rs`.

### Status: SETTLED v0.0.8.

### DO NOT RETRY
- Every new `SerializerConfig` field needs both a builder test
  AND an emit-path assertion. Do not merge a config knob with
  builder coverage only — that is exactly how this bug shipped.

---

## Entry 8 — Issue #46 depth-counter imbalances (v0.0.6)

### Symptom
User-reported: `pnpm-lock.yaml` (10k+ lines but only ~5 levels
deep) failed `from_str::<Value>` with
`Error::RecursionLimitExceeded { depth: 129 }` under default
`max_depth = 128`. Raising to 200–300 then stack-overflowed.

### Root cause (two peers, one campaign)
**Peer A — streaming depth leak on empty flow mappings.**
`StreamingMapAccess::next_key_seed` did not check the access
object's `finished` flag. Serde visitors that call `next_entry`
after `next_key` returned `Ok(None)` — canonical example:
`ValueVisitor::visit_map` — re-entered, peeked the **next key of
the parent mapping**, treated it as belonging to the exhausted
inner map, recursed into `deserialize_any`, hit `MappingStart`,
incremented `depth`, called `visit_map` again. Depth grew by one
per empty `{}` entry.

**Peer B — NoSpan path missing `max_depth` check.**
The span-tracked loader at `parser/loader.rs:399, 443` fired
`RecursionLimitExceeded` on every `SequenceStart`/`MappingStart`.
The companion `NoSpanLoader` incremented `depth` at lines 814/833
but **never compared it against the limit**. Adversarial nesting
consumed stack without ever surfacing the documented DoS guard.

### Evidence
- Peer A: `6991350` — "fix(streaming): stop depth leak on empty
  flow mappings (#46)", `crates/noyalib/src/streaming.rs`.
- Peer B: `ad28829` — "fix(loader): NoSpan path was missing the
  max_depth check (#46 audit)", `crates/noyalib/src/parser/loader.rs`.
- Regression test: `no_span_loader_honours_max_depth` in
  `crates/noyalib/tests/issue_46.rs` — 200-level sequence asserts
  `Err(RecursionLimitExceeded { depth })` with `depth > 128`.
- Ships in `df17887` — v0.0.6 batch.

### Status: SETTLED v0.0.6. Family audit at fix time confirmed no
other `MapAccess`/`SeqAccess`/`EnumAccess`/`VariantAccess` impl
in the crate has this pattern.

### DO NOT RETRY
- Do not add a new `MapAccess` / `SeqAccess` impl without a
  `finished` flag consulted from **both** `next_key_seed` and
  `next_value_seed`.
- Do not add a new load path without a `max_depth` check on
  every `MappingStart` / `SequenceStart`. Every load path is a
  DoS surface.
- Do not raise default `max_depth` above 128 as a workaround for
  a depth-counter bug. The counter is wrong, not the limit.

---

## Entry 9 — RUSTSEC responses & cargo-vet trust-chain gaps

### Symptom
A dependency version that closes a `RUSTSEC-*` advisory ships
from a publisher **outside** the `[[trusted.<crate>]]` entry in
`supply-chain/audits.toml`. CI's `cargo vet check` reports
`<crate>:<version> missing ["safe-to-deploy"]`; the release PR
turns red for a reason unrelated to the loader fix on the branch.

### Root cause
`cargo-vet` trust is scoped by publisher user-id, not by crate
name. A publisher change breaks the trust chain even when the
bump is legitimate.

### Evidence
- `3e8dcb8` — "fix(ci): rustfmt + RUSTSEC-2026-0204 (crossbeam-
  epoch < 0.9.20)". `cargo update -p crossbeam-epoch` to 0.9.20.
- `9de0321` — "fix(supply-chain): exempt crossbeam-epoch 0.9.20
  for cargo-vet". Adds `[[exemptions.crossbeam-epoch]]` with
  `suggest = false` because the new publisher wasn't in the
  `[[trusted.crossbeam-epoch]]` user-id entry (Taiki Endo, 33035).
- **Gotcha: `cargo vet fmt` strips TOML comments.** Rationale
  must live in the commit message body, not inline.

### Pattern
1. Advisory lands (Dependabot / manual audit).
2. `cargo update -p <crate>` to the fixed version.
3. `cargo vet check`. If trust chain holds, done.
4. If not: add `[[exemptions.<crate>]]` with `suggest = false`
   and rationale in the **commit message**.

### Status: SETTLED as doctrine.

### DO NOT RETRY
- Do not put exemption rationale in a TOML comment — `cargo vet
  fmt` deletes it on the next run.
- Do not "extend trust" without an actual audit — defeats the
  vet system.
- Do not batch a RUSTSEC bump into a large release without
  budgeting for a CI storm.

---

## Entry 10 — Workspace-split shared-workflow caller permissions (ADR-0005, v0.0.12–13)

### Symptom
First CI run on the `noyalib-wasm` satellite pilot **startup-
failed with 0 jobs and no annotation**. Actions UI showed nothing
green/red/anything.

### Root cause
Reusable workflows: the callee declared
`permissions: pull-requests: read`. The caller `ci.yml` only
granted `contents: read`. Actions rejects the whole workflow
when the callee's `permissions` block requests scopes the caller
did not grant — **silently**, 0 jobs, no annotation.

### Evidence
- `fccd189` — "chore(workspace-split): crates.io ownership harness
  + ADR-0005 (#135)". Introduces shared workflow model.
- `5e98151` — "docs(adr): document caller-side permissions
  gotcha (v0.0.12 pilot)". Adds permissions-mapping table to
  `doc/adr/0005-workspace-split.md`.
- Phases: `e695d4a` (1), `f984e3b` (2), `69e3bf3` (3),
  `33491ae` (4). Satellite completion: `a472e14`.

### Fix pattern
Every satellite `ci.yml` must **union** the permissions of every
shared workflow it calls. ADR-0005 carries the mapping table.

### Status: SETTLED as doctrine.

### DO NOT RETRY
- Do not diagnose a 0-jobs-no-annotation startup-fail as a
  "flaky runner". It is almost always a permissions mismatch.
- Do not narrow a shared workflow's `permissions` block after
  release without auditing every satellite caller.
- Do not use `permissions: write-all` in a satellite to sidestep
  the union — supply-chain regression on every job that didn't
  need write.

---

## How to add an entry

Copy this skeleton above the "Provenance" section of `SKILL.md`
(or append here and add a row to the index). If you can't fill
"Root cause", the incident is not yet settled — file an issue
instead.

```markdown
## Entry N — <short description> (<version or date>)

### Symptom
<what CI or the user saw. Concrete. Code snippet if possible.>

### Root cause
<one or two paragraphs. List peers if any.>

### Evidence
- Fix commit `<sha>` — "<subject>", `<file path>`.
- Regression test: `<path>`.
- Related release notes: `RELEASE-NOTES-v<version>.md`.

### Status: SETTLED <version or date>
<one line on scope.>

### DO NOT RETRY
- <specific rejected fix path>
- <invariant the fix relies on>
```

Adding checklist:
1. `git log --oneline --all | grep <sha>` — verify SHA exists.
2. `git show <sha> -s --format="%h %s%n%n%b"` — read the body.
   Subject lines here are often misleading.
3. If the fix touched multiple files, list the primary one under
   Evidence and mention others by directory.
4. Cross-reference in "See also" of related entries and update
   the index row in `SKILL.md`.

---

## SHA re-verification one-liner

All 25 commits below were live in `main` on 2026-07-07. Re-verify:

```sh
# All SHAs referenced exist:
for sha in 5104048 0b2d616 f984e3b bc8f798 0fff9dd 9bef479 1e507e4 \
          71de2d9 3304f4c 70c77cb 3ad36f0 f8fe929 34852b2 c528e0f \
          6991350 ad28829 df17887 3e8dcb8 9de0321 fccd189 5e98151 \
          e695d4a 69e3bf3 33491ae a472e14; do
  git log --oneline --all | grep -q "^$sha" && echo "OK  $sha" \
    || echo "MISSING $sha"
done

# Read a specific incident's long-form commit body:
git show <sha> -s --format="%h %s%n%n%b"

# Search peers of a settled bug by keyword:
git log --all --oneline --grep="<keyword>" -i

# Cross-reference to release notes:
ls RELEASE-NOTES-v0.0.*.md
```

Long-form commit bodies are ground truth; release notes are a
readable secondary; issue numbers (`#118`, `#149`, `#152`, `#46`,
`#84`, `#147`) are stable GitHub pointers.
