---
name: noyalib-architecture-contract
description: Load-bearing design decisions, invariants, and residual weak points for noyalib's parser/loader/CST. Use before modifying scanner/loader/streaming/CST code, adding a config axis or budget, wiring a new deserialise entry point, answering "can I change X here", "why are there three loaders", "which path enforces this limit", "explain the three-loader architecture", "what is a NoSpanLoader", "what invariants must I preserve when editing loader.rs", "what does loader-parity require", or reviewing a PR that touches de.rs / parser/loader.rs / cst/document.rs. Not a runbook for CI/release — see noyalib-ci-and-release. Not incident detail — see noyalib-failure-archaeology.
---

# noyalib architecture contract

**Version:** v0.0.14 · **Date-stamp:** 2026-07-08 · **Audience:** mid-level engineer or Sonnet-class model about to modify parser / loader / streaming / CST code.

> **Reference material** (verbatim routing snippet, exhaustive
> invariant table, detailed rustdoc excerpts, full known-weak-points
> rationale): see `reference.md` in this directory. Load when you
> need file:line citations beyond the top few, the verbatim
> `stream_eligible` conjunction, the `value_target_bypass`
> two-clause explanation, or the extended weak-points writeup.

This skill exists to keep the three most load-bearing decisions in the
library from silently drifting. If you skip it, the failure mode is
not a compile error — it is an invariant that used to hold quietly and
now doesn't, discovered weeks later in a downstream bug report.

The workspace-wide `#![forbid(unsafe_code)]` policy (ADR-0003) is
non-negotiable: no exceptions, no `unsafe` blocks, no
`#[allow(unsafe_code)]`. This is orthogonal to the loader parity
contract but is the second axis of the panic-free / memory-safe
posture the library ships on.

---

## 1. The three-loader architecture (the single most load-bearing decision)

noyalib ships **three** paths from a `&str` to a Rust value. They
share a scanner and event stream; they diverge on what they build
downstream.

| Path | What it produces | When it runs | Owner file |
|---|---|---|---|
| **StreamingDeserializer** | typed `T` directly (no AST) | `from_str::<T>` where `T` is typed (struct, scalar, `Vec<Struct>`, …) and every config axis is default | `crates/noyalib/src/streaming.rs` |
| **Span-full `Loader`** | `(Value, SpanTree)` pair, drives `Spanned<T>` and policies | `from_str::<T>` with `T ≠ Value` on the `std` build when streaming is skipped | `crates/noyalib/src/parser/loader.rs` (`Loader`, `Frame`) |
| **Span-free `NoSpanLoader`** | `Value` only, no SpanTree, no thread-local | `from_str::<Value>` and every `no_std` build | `crates/noyalib/src/parser/loader.rs` (`NoSpanLoader`, `NoSpanFrame`, `load_one_no_spans`) |

### Routing summary

The router lives in `from_str_with_config` (`de.rs:392`). Order:

1. Compute `value_target_bypass = is_value_target::<T>() && config.tag_registry.is_none()` (`de.rs:415`).
2. Compute `stream_eligible` as a conjunction over `merge_key_policy`, `ignore_binary_tag_for_string`, `policies`, `properties`, `includes`, and `!value_target_bypass` (`de.rs:416-421`). Take the streaming path if true.
3. Unconditionally re-check `max_document_length` (`de.rs:436-441`) — streaming enforces inline; skip-streaming branches wouldn't otherwise.
4. If `is_value_target::<T>()` → `parse_one_value` → `NoSpanLoader`, then downcast `Box<dyn Any>` back to `T` (`de.rs:454-470`).
5. Else (`std`) → `parse_one` → span-full `Loader` → `build_span_map` → `set_span_context` → serde reads TLS `SpanContext` (`de.rs:472+`).
6. `no_std` always takes step 4 — `Spanned<T>` is `std`-only.

**Verbatim `stream_eligible` snippet and the `value_target_bypass`
two-clause reasoning: `reference.md` §R1.1-R1.3.**

### Why three (not one) — one-line each

1. **Streaming for the 95% case** — no `Value`, no `SpanTree`, no second serde walk.
2. **Span-full loader for `Spanned<T>` and policies** — TLS span context + walkable tree.
3. **Span-free loader for `from_str::<Value>`** — `Value::deserialize` never consults spans.

Extended rationale: `reference.md` §R1.4.

### The parity contract (load-bearing)

**Every new budget, policy check, or invariant MUST be added to (a)
the streaming path in `streaming.rs`, (b) `Loader::process_event`,
(c) `NoSpanLoader::process_event`, AND a cross-path test in
`crates/noyalib/tests/` that asserts identical behaviour.**
`typed_keys` (distinct-typed key collision detection) is the canonical
worked example, with the streaming path's residual gap for typed
targets logged as §5.2. Full worked example with citations:
`reference.md` §R1.5.

**CI companion — cache-poisoning doctrine.** Loader-parity is half
the invariant; the other half is that CI actually runs all three paths
with distinct fingerprints. Any new compile-surface (new feature
combination, sanitiser, toolchain leg) MUST get its own
`CARGO_TARGET_DIR`. See `noyalib-ci-and-release` §2 and the memory
`feedback_ci_cache_poisoning`.

---

## 2. Invariants that must hold

Break one and the failure will not be a compiler diagnostic — it will
be a silent correctness bug. Top-priority invariants stay here; the
exhaustive table with every file:line citation is in
`reference.md` §R2.

| Invariant | Where enforced | Failure mode if broken |
|---|---|---|
| `typed_keys` stays parallel to `Mapping` in both loaders | `loader.rs:1170-1174` (`debug_assert_eq!` in `NoSpanLoader::push_value`); mirror in span-full loader arms `loader.rs:701-731` | Distinct-typed collision misfires — false positives, or silent `1`/`"1"` merges. |
| Panic-free contract on well-formed input | POLICIES.md §8. Sanctioned panic sites: `crate::error::invariant_violated(msg) -> !` (`error.rs:1697`, `#[cold]`, `#[inline(never)]`) and allocator OOM. Scanner's `slice_str` defensively clamps via `floor_char_boundary` (`scanner.rs:588-595, 2070+`). | Any panic on well-formed input is a bug and must ship with a regression test in the same PR. The two `panic!` sites in `scanner.rs:2104, :2148` are inside `#[cfg(test)]` helpers — safe. |
| `Mapping<String, Value>` keys are strings; distinct-typed collisions error loudly with `Error::KeyCollision(key)` | `loader.rs:684-696` (span-full), `loader.rs:1143-1152` (span-free), returned **before** falling through to `DuplicateKeyPolicy`. | Silent data loss: `1: a\n"1": b\n` collapses to one entry. **Streaming path has no equivalent check for typed targets** — §5.2. |
| Alias budgets checked on **every** alias dereference | `loader.rs:352-400` (span-full), `loader.rs:917-950` (span-free); streaming has its own equivalent. `MAX_ALIAS_BYTES = 32 MB` hard cap at `loader.rs:19`. | Billion-laughs regression. Add-a-checkpoint-to-only-one-loader is the canonical parity incident. |
| `depth += 1` on Sequence/Mapping-Start is matched by `depth = depth.saturating_sub(1)` on **both** Ok and Err paths | `loader.rs:464, 480, 511, 529, 990, 1004, 1015, 1031`; streaming counterpart tagged `issue #46` at `streaming.rs:663, 681, 942, 979, 1183`. | Depth leaks upward across sibling collections; `max_depth` fires spuriously. |

Full table (scanner trivia, anchor byte accumulation, `SpanContextGuard`
drop clearing TLS, plus all citations): `reference.md` §R2.

---

## 3. CST green-tree design (ADR-0001)

The CST is a **parallel side-table**, not a unified AST. Two products
from one parse:

- `Value` (the data path) — allocates only what the data demands, no trivia.
- `noyalib::cst::Document` (the tooling path) — retains every byte of source; `Document::to_string()` on an unmutated tree is byte-identical to the input.

Both consume the same scanner token stream. There is no second parser.

**Byte-for-byte source reproduction** — `GreenChild::Token { text:
Box<str> }` carries the exact source bytes; nodes carry `text_len:
usize` and `children: Arc<[GreenChild]>`. The concatenation of every
leaf's text in document order equals the input.

### `span_at` semantics (summary)

`Document::span_at(path) -> Option<(usize, usize)>` (`document.rs:193`)
resolves a JSON-path-shaped selector to a byte span. Three subtleties
every future edit must preserve:

1. `trim_value_span` (`document.rs:1544`) trims trailing separator whitespace/newlines.
2. `is_keep_chomped_block_scalar` (`document.rs:1558`) short-circuits `trim_value_span` for `|+` / `>+`.
3. `extend_to_line_start` (`document.rs:1340`) — block collection values include their first line's indent.

Detailed rationale, typed-cache fallback behaviour, and CST
throughput ADR-0001 trade-off (~21 MB/s vs ~36 MB/s): `reference.md` §R3.

---

## 4. SemVer / API contract (from `lib.rs` rustdoc, §"API stability and SemVer policy" at `lib.rs:111-157`)

- **Pre-1.0 breaking axis is the patch number** during the `0.0.x` series. `0.0.14 → 0.0.15` *is* the breaking bump. Memory `project_v001_launch_posture`: runway is `0.0.x → 0.0.99 → 0.0.999 → 0.1.0`.
- **`#[non_exhaustive]` on every public config struct and every error type.** Adding a field or variant is not breaking; do not remove the attribute "because it's convenient."
- **Deserialise bound is `T: for<'de> Deserialize<'de> + 'static`.** The `'static` half enables `is_value_target::<T>()`; `from_str_typed_no_tag_preserve` (`de.rs:189`) is the internal escape hatch for callers like `figment::Format::from_str` that drop `'static`.
- **CI enforces the surface** via `cargo semver-checks` on every PR.

Full list of `#[non_exhaustive]` types and the detailed rustdoc excerpt:
`reference.md` §R4.

---

## 5. Known-weak points, stated plainly

Terse summary; per-item detailed rationale in `reference.md` §R5.

1. **`max_sequence_length` / `max_mapping_keys` surface as `Error::Serialize`, not `Error::Budget`** — classifier wart from v0.0.13. Noted for v0.0.15: add `BudgetBreach::MaxMappingKeys` / `MaxSequenceLength` variants, reroute both call sites in both loaders, cross-path parity tests. §R5.1.
2. **Streaming path has no distinct-typed key collision check for typed targets** — serde receives `String` keys, stringifying `1`/`"1"` before the check could run. `value_target_bypass` routes `Value` targets around streaming; typed targets like `HashMap<String, T>` on streaming do not get `KeyCollision`. §R5.2.
3. **Coverage below the 98% target** — current gates 96/94/93 (functions/lines/regions) in `.github/workflows/ci.yml:160-162` and `shared-coverage.yml`. `doc/TESTING.md` cites stale `95/93/92`; trust the workflow files. Do not lower gates to make a PR pass. §R5.3.
4. **Single-maintainer bus factor** — GOVERNANCE.md 1.0-gate: at least one non-@sebastienrousseau maintainer with commit + release-signing rights. Bus factor is 1 until then. §R5.4.
5. **CST throughput ~21 MB/s vs `Value` ~36 MB/s** — not a bug; ADR-0001 trade-off. §R5.5.

---

## 6. When to use a different skill

| Question | Skill |
|---|---|
| CI is red / release cadence / cargo-vet exemptions / crates.io publish flow | `noyalib-ci-and-release` |
| Past incidents in depth (v0.0.14 loader parity, CI cache poisoning, shared-workflow permissions) | `noyalib-failure-archaeology` |
| Config axis names, feature flag matrix, `ParserConfig::strict()` defaults | `noyalib-config-and-flags` |
| PR review checklist, breaking-change classification | `noyalib-change-control` |
| YAML 1.2 spec resolution table, plain-scalar coercion | `yaml-domain-reference` |
| Debugging a failed parse (which loader ran, why did it error) | `noyalib-debugging-playbook` |

---

## 7. Provenance / re-verify

Every claim in this skill (and in `reference.md`) maps to a file:line.
This provenance section covers **both files** in this directory.
Re-verify on drift with:

```bash
# Router / streaming-eligibility / typed_keys parity
grep -n "stream_eligible" /Users/seb/Code/Public/rust/noyalib/crates/noyalib/src/de.rs
grep -n "typed_keys" /Users/seb/Code/Public/rust/noyalib/crates/noyalib/src/parser/loader.rs | head -5
grep -n "issue #46" /Users/seb/Code/Public/rust/noyalib/crates/noyalib/src/streaming.rs
grep -n "MAX_ALIAS_BYTES" /Users/seb/Code/Public/rust/noyalib/crates/noyalib/src/parser/loader.rs

# Panic policy / SemVer surface / weak-points / CST span_at
grep -rn "invariant_violated" /Users/seb/Code/Public/rust/noyalib/crates/noyalib/src/
grep -n "non_exhaustive\|'static\b\|SemVer" /Users/seb/Code/Public/rust/noyalib/crates/noyalib/src/lib.rs | head
grep -n "sequence length limit exceeded\|mapping key limit exceeded" /Users/seb/Code/Public/rust/noyalib/crates/noyalib/src/parser/loader.rs
grep -n "trim_value_span\|extend_to_line_start\|is_keep_chomped" /Users/seb/Code/Public/rust/noyalib/crates/noyalib/src/cst/document.rs | head
```

Ground-truth documents this skill (and `reference.md`) compress:

- `doc/ARCHITECTURE.md` — workspace layout, end-to-end pipelines, streaming/loader/CST phases
- `doc/adr/0001-cst-rowan-shape.md` — parallel green tree, not unified AST
- `doc/adr/0002-yaml-1.2-default.md` — YAML 1.2 default, 1.1 opt-in via `legacy_*` flags
- `doc/adr/0003-zero-unsafe-policy.md` — `#![forbid(unsafe_code)]` workspace-wide, no exceptions
- `doc/adr/0005-workspace-split.md` — satellite crates in their own repos, strict-lockstep versioning
- `doc/design/green-tree.md` — CST design note, ~480 lines
- `doc/POLICIES.md` §8 — panic policy (canonical panic sites)
- `crates/noyalib/src/lib.rs` — module map, SemVer policy rustdoc section
- `crates/noyalib/src/de.rs` — `from_str_with_config` router
- `crates/noyalib/src/parser/loader.rs` — `Loader` + `NoSpanLoader`
- `crates/noyalib/src/parser/scanner.rs` — defensive `slice_str` / `floor_char_boundary`
- `crates/noyalib/src/span_context.rs` — TLS-backed `SpanContext`
- `crates/noyalib/src/error.rs` — `BudgetBreach`, `ErrorKind`, `invariant_violated`
